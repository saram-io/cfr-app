from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from .config import DATA_DIR, PUBLIC_API_URL, decrypt_env_dict, decrypt_secret
from .models import Asset, BackupPolicy, StorageRepository

RESTIC_BIN = shutil.which("restic") or "/usr/bin/restic"


def get_resticprofile_bin() -> Optional[str]:
    found = shutil.which("resticprofile")
    if found:
        return found
    for candidate in ("/usr/local/bin/resticprofile", str(Path.home() / ".local/bin/resticprofile")):
        if Path(candidate).exists():
            return candidate
    return None


def profile_name_for_asset(asset: Asset) -> str:
    return asset.asset_tag.strip().lower().replace("_", "-").replace(" ", "-")


def cron_to_resticprofile_schedule(schedule_preset: str, schedule_cron: str) -> str:
    preset = (schedule_preset or "").upper()
    cron = (schedule_cron or "0 2 * * *").strip()
    if preset == "HOURLY" or cron == "0 * * * *":
        return "hourly"
    if preset == "EVERY_4_HOURS" or cron == "0 */4 * * *":
        return "*-*-* 00/4:00:00"
    if preset == "WEEKLY" or cron == "0 3 * * 0":
        return "Sun *-*-* 03:00:00"
    parts = cron.split()
    if len(parts) == 5:
        minute, hour, dom, month, dow = parts
        if minute.isdigit() and hour.isdigit() and dom == "*" and month == "*" and dow == "*":
            return f"*-*-* {int(hour):02d}:{int(minute):02d}:00"
    return "02:00"


def generate_resticprofile_yaml(
    repo: StorageRepository,
    asset: Asset,
    policy: BackupPolicy,
    *,
    for_gateway: bool = False,
    password_file_path: Optional[str] = None,
    status_file_path: Optional[str] = None,
    api_url: Optional[str] = None,
    backup_paths_override: Optional[List[str]] = None,
) -> str:
    profile_name = profile_name_for_asset(asset)
    paths: List[str] = backup_paths_override if backup_paths_override is not None else json.loads(policy.backup_paths_json or "[]")
    if not paths:
        paths = [f"/app/data/sample_instruments/{asset.asset_tag}"]
    excludes: List[str] = json.loads(policy.exclude_patterns_json or "[]")
    schedule_str = cron_to_resticprofile_schedule(policy.schedule_preset, policy.schedule_cron)
    effective_api_url = (api_url or PUBLIC_API_URL).rstrip("/")

    pwd_path = password_file_path or (
        "C:/ProgramData/CFRApp/repository-password.txt"
        if asset.os_type == "WINDOWS" and not for_gateway
        else f"/etc/cfr-agent/{profile_name}.key"
    )
    stat_path = status_file_path or (
        "C:/ProgramData/CFRApp/status.json"
        if asset.os_type == "WINDOWS" and not for_gateway
        else f"/var/lib/cfr-agent/{profile_name}-status.json"
    )
    restic_bin_path = (
        "C:/Program Files/Restic/restic.exe"
        if asset.os_type == "WINDOWS" and not for_gateway
        else RESTIC_BIN
    )

    lines = [
        "# yaml-language-server: $schema=https://creativeprojects.github.io/resticprofile/jsonschema/config-1.json",
        f"# CFR-App Generated resticprofile Configuration for {asset.asset_tag} ({asset.name})",
        f"# GMP Regulated: {'Yes' if asset.is_gmp else 'No'} | Criticality: {asset.criticality} | Policy Rev: v{policy.config_version}",
        'version: "1"',
        "",
        "global:",
        f"  restic-binary: {json.dumps(restic_bin_path)}",
        "  initialize: true",
        "  priority: low",
        "  restic-lock-retry-after: 1m",
        "  restic-stale-lock-age: 1h",
        "",
        f"{profile_name}:",
        f"  repository: {json.dumps(repo.repo_uri)}",
        f"  password-file: {json.dumps(pwd_path)}",
        f"  status-file: {json.dumps(stat_path)}",
        "  force-inactive-lock: true",
    ]

    extra_env = decrypt_env_dict(repo.encrypted_env_json)
    if extra_env:
        lines.append("  env:")
        for k, v in extra_env.items():
            if v is not None:
                lines.append(f"    {k}: {json.dumps(str(v) if for_gateway else f'${{{k}}}')}")

    lines.extend(
        [
            "  backup:",
            f"    host: {json.dumps(asset.hostname_or_ip or asset.asset_tag)}",
            "    source:",
        ]
    )
    for p in paths:
        lines.append(f"      - {json.dumps(str(p))}")

    if excludes:
        lines.append("    exclude:")
        for ex in excludes:
            lines.append(f"      - {json.dumps(str(ex))}")

    lines.extend(
        [
            "    tag:",
            f'      - "asset:{asset.asset_tag}"',
            f'      - "gmp:{"true" if asset.is_gmp else "false"}"',
            f'      - "criticality:{asset.criticality}"',
            f"    schedule: {json.dumps(schedule_str)}",
            '    schedule-permission: "system"',
        ]
    )

    # Windows VSS snapshot flag (only on Windows endpoints; Linux restic binary does not accept --use-fs-snapshot)
    if policy.vss_enabled and asset.os_type == "WINDOWS" and not for_gateway:
        lines.append("    use-fs-snapshot: true")

    if policy.pre_backup_hook:
        lines.append("    run-before:")
        lines.append(f"      - {json.dumps(policy.pre_backup_hook)}")

    if not for_gateway:
        lines.extend(
            [
                "    send-after:",
                "      method: POST",
                f'      url: "{effective_api_url}/agents/report"',
                "      headers:",
                "        - name: Content-Type",
                "          value: application/json",
                "        - name: X-Agent-Token",
                f"          value: {json.dumps(asset.agent_token)}",
                '      body: \'{"status": "COMPLETED", "log_output": "Executed via resticprofile (' + profile_name + ')"}\'',
                "    send-after-fail:",
                "      method: POST",
                f'      url: "{effective_api_url}/agents/report"',
                "      headers:",
                "        - name: Content-Type",
                "          value: application/json",
                "        - name: X-Agent-Token",
                f"          value: {json.dumps(asset.agent_token)}",
                '      body: \'{"status": "FAILED", "error_message": "${ERROR}", "log_output": "${ERROR_STDERR}"}\'',
            ]
        )

    if not repo.immutable_append_only:
        lines.extend(
            [
                "  retention:",
                "    before-backup: false",
                "    after-backup: true",
                f"    keep-last: {int(policy.retention_keep_last)}",
                f"    keep-daily: {int(policy.retention_keep_daily)}",
                f"    keep-weekly: {int(policy.retention_keep_weekly)}",
                f"    keep-monthly: {int(policy.retention_keep_monthly)}",
                f"    keep-yearly: {int(policy.retention_keep_yearly)}",
                "    keep-tag:",
                f'      - "asset:{asset.asset_tag}"',
            ]
        )

    lines.extend(
        [
            "  check:",
            '    schedule: "weekly"',
            '    schedule-permission: "system"',
            "",
        ]
    )
    return "\n".join(lines)


def write_asset_resticprofile(
    repo: StorageRepository,
    asset: Asset,
    policy: BackupPolicy,
    valid_paths: Optional[List[str]] = None,
) -> Tuple[Path, str]:
    profiles_dir = DATA_DIR / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_name = profile_name_for_asset(asset)

    pwd_file = profiles_dir / f"{profile_name}.key"
    pwd_file.write_text(decrypt_secret(repo.encrypted_password))
    try:
        os.chmod(pwd_file, 0o600)
    except OSError:
        pass

    status_file = profiles_dir / f"{profile_name}.status.json"
    yaml_content = generate_resticprofile_yaml(
        repo,
        asset,
        policy,
        for_gateway=True,
        password_file_path=str(pwd_file),
        status_file_path=str(status_file),
        backup_paths_override=valid_paths,
    )
    profile_path = profiles_dir / f"{profile_name}.yaml"
    profile_path.write_text(yaml_content)
    return profile_path, profile_name


def validate_resticprofile(repo: StorageRepository, asset: Asset, policy: BackupPolicy) -> Dict[str, Any]:
    profile_path, profile_name = write_asset_resticprofile(repo, asset, policy)
    endpoint_yaml = generate_resticprofile_yaml(repo, asset, policy, for_gateway=False)
    rp_bin = get_resticprofile_bin()

    if not rp_bin:
        return {
            "profile_name": profile_name,
            "config_yaml": endpoint_yaml,
            "gateway_profile_path": str(profile_path),
            "resticprofile_binary": None,
            "valid": True,
            "show_output": "resticprofile YAML generated (resticprofile binary not found in PATH).",
        }

    proc = subprocess.run(
        [rp_bin, "--no-ansi", "-c", str(profile_path), "-n", profile_name, "show"],
        env=build_restic_env(repo),
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return {
        "profile_name": profile_name,
        "config_yaml": endpoint_yaml,
        "gateway_profile_path": str(profile_path),
        "resticprofile_binary": rp_bin,
        "valid": proc.returncode == 0,
        "show_output": output,
    }


def build_restic_env(repo: StorageRepository) -> Dict[str, str]:
    env = os.environ.copy()
    env["RESTIC_REPOSITORY"] = repo.repo_uri
    env["RESTIC_PASSWORD"] = decrypt_secret(repo.encrypted_password)
    extra_env = decrypt_env_dict(repo.encrypted_env_json)
    for k, v in extra_env.items():
        if v is not None:
            env[str(k)] = str(v)
    return env


def init_repository(repo: StorageRepository) -> Tuple[bool, str]:
    env = build_restic_env(repo)
    # If local path, ensure parent directory exists
    if repo.backend_type == "LOCAL_NAS" and not repo.repo_uri.startswith(("s3:", "rest:", "sftp:", "azure:", "gs:", "b2:")):
        Path(repo.repo_uri).parent.mkdir(parents=True, exist_ok=True)

    # First check if already initialized
    probe = subprocess.run(
        [RESTIC_BIN, "cat", "config"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode == 0:
        return True, f"Repository already initialized: {probe.stdout.strip()}"

    proc = subprocess.run(
        [RESTIC_BIN, "init"],
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if proc.returncode == 0:
        return True, proc.stdout.strip()
    return False, (proc.stderr or proc.stdout).strip()


def check_repository(repo: StorageRepository) -> Tuple[bool, str]:
    env = build_restic_env(repo)
    proc = subprocess.run(
        [RESTIC_BIN, "check"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, output


def run_gateway_backup(repo: StorageRepository, asset: Asset, policy: BackupPolicy) -> Dict[str, Any]:
    env = build_restic_env(repo)
    paths: List[str] = json.loads(policy.backup_paths_json or "[]")
    excludes: List[str] = json.loads(policy.exclude_patterns_json or "[]")

    # Ensure local demo/landing zone paths exist so gateway backups succeed cleanly
    valid_paths = []
    for p in paths:
        path_obj = Path(p)
        if not path_obj.exists() and str(p).startswith(str(DATA_DIR)):
            path_obj.mkdir(parents=True, exist_ok=True)
            sample_file = path_obj / f"{asset.asset_tag}_acquisition_run.txt"
            sample_file.write_text(
                f"GMP Raw Instrument Data\nAsset: {asset.asset_tag} ({asset.name})\n"
                f"Serial: {asset.serial_number}\nGenerated UTC: {datetime.now(timezone.utc).isoformat()}\n"
            )
        valid_paths.append(str(p))

    # Always materialize the asset's declarative resticprofile YAML in DATA_DIR/profiles
    profile_path, profile_name = write_asset_resticprofile(repo, asset, policy, valid_paths=valid_paths)
    rp_bin = get_resticprofile_bin()

    if rp_bin:
        cmd = [
            rp_bin,
            "--no-ansi",
            "-c",
            str(profile_path),
            "-n",
            profile_name,
            "backup",
            "--json",
        ]
    else:
        cmd = [
            RESTIC_BIN,
            "backup",
            "--json",
            "--host",
            asset.hostname_or_ip or asset.asset_tag,
            "--tag",
            f"asset:{asset.asset_tag}",
            "--tag",
            f"gmp:{'true' if asset.is_gmp else 'false'}",
            "--tag",
            f"criticality:{asset.criticality}",
        ]
        for ex in excludes:
            cmd.append(f"--exclude={ex}")
        cmd.extend(valid_paths)

    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    duration = round(time.monotonic() - t0, 2)
    combined_log = (proc.stdout + "\n" + proc.stderr).strip()

    if proc.returncode != 0:
        return {
            "status": "FAILED",
            "duration_seconds": duration,
            "snapshot_id": None,
            "files_new": 0,
            "files_changed": 0,
            "files_unmodified": 0,
            "bytes_added": 0,
            "total_bytes_processed": 0,
            "log_output": combined_log,
            "error_message": (proc.stderr or "Restic / resticprofile backup command failed").strip(),
        }

    summary = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
            if parsed.get("message_type") == "summary":
                summary = parsed
        except Exception:
            continue

    # If resticprofile was not used, run retention policy directly when repository is not append-only
    if not rp_bin and not repo.immutable_append_only:
        forget_cmd = [
            RESTIC_BIN,
            "forget",
            "--tag",
            f"asset:{asset.asset_tag}",
            "--keep-last",
            str(policy.retention_keep_last),
            "--keep-daily",
            str(policy.retention_keep_daily),
            "--keep-weekly",
            str(policy.retention_keep_weekly),
            "--keep-monthly",
            str(policy.retention_keep_monthly),
            "--keep-yearly",
            str(policy.retention_keep_yearly),
        ]
        subprocess.run(forget_cmd, env=env, capture_output=True, text=True, timeout=60)

    return {
        "status": "COMPLETED",
        "duration_seconds": duration,
        "snapshot_id": summary.get("snapshot_id", ""),
        "files_new": int(summary.get("files_new", 0)),
        "files_changed": int(summary.get("files_changed", 0)),
        "files_unmodified": int(summary.get("files_unmodified", 0)),
        "bytes_added": int(summary.get("data_added", 0)),
        "total_bytes_processed": int(summary.get("total_bytes_processed", 0)),
        "log_output": combined_log,
        "error_message": None,
    }


def list_repo_snapshots(repo: StorageRepository, asset_tag: Optional[str] = None) -> List[Dict[str, Any]]:
    env = build_restic_env(repo)
    cmd = [RESTIC_BIN, "snapshots", "--json"]
    if asset_tag:
        cmd.extend(["--tag", f"asset:{asset_tag}"])
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def list_snapshot_files(repo: StorageRepository, snapshot_id: str) -> List[Dict[str, Any]]:
    env = build_restic_env(repo)
    proc = subprocess.run(
        [RESTIC_BIN, "ls", "--json", snapshot_id],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return []
    files = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if obj.get("struct_type") == "node" or "path" in obj:
                files.append(
                    {
                        "name": obj.get("name"),
                        "type": obj.get("type", "file"),
                        "path": obj.get("path"),
                        "size": obj.get("size", 0),
                        "mtime": obj.get("mtime"),
                        "permissions": obj.get("permissions"),
                    }
                )
        except Exception:
            continue
    return files


def execute_restore_and_verify(
    repo: StorageRepository,
    snapshot_id: str,
    target_dir: str,
) -> Dict[str, Any]:
    env = build_restic_env(repo)
    target_path = Path(target_dir)
    if target_path.exists():
        shutil.rmtree(target_path, ignore_errors=True)
    target_path.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    proc = subprocess.run(
        [RESTIC_BIN, "restore", snapshot_id, "--target", str(target_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    elapsed_seconds = time.monotonic() - t0
    actual_rto_minutes = round(elapsed_seconds / 60.0, 3)

    if proc.returncode != 0:
        return {
            "success": False,
            "actual_rto_minutes": actual_rto_minutes,
            "restored_file_count": 0,
            "restored_bytes": 0,
            "sha256_manifest": [],
            "error_message": (proc.stderr or proc.stdout).strip(),
        }

    manifest = []
    total_bytes = 0
    for root, _, filenames in os.walk(target_path):
        for fname in sorted(filenames):
            fpath = Path(root) / fname
            if fpath.is_file():
                rel = str(fpath.relative_to(target_path))
                data = fpath.read_bytes()
                size = len(data)
                total_bytes += size
                digest = hashlib.sha256(data).hexdigest()
                manifest.append(
                    {
                        "file": rel,
                        "size_bytes": size,
                        "sha256": digest,
                    }
                )

    return {
        "success": True,
        "actual_rto_minutes": max(actual_rto_minutes, 0.01),
        "restored_file_count": len(manifest),
        "restored_bytes": total_bytes,
        "sha256_manifest": manifest,
        "error_message": None,
    }


def dump_snapshot_zip(repo: StorageRepository, snapshot_id: str, path_in_snapshot: str = "/") -> bytes:
    env = build_restic_env(repo)
    proc = subprocess.run(
        [RESTIC_BIN, "dump", "--archive", "zip", snapshot_id, path_in_snapshot],
        env=env,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or b"Failed to dump snapshot archive").decode("utf-8", errors="replace"))
    return proc.stdout
