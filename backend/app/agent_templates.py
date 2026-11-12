import json
from .config import PUBLIC_API_URL, encrypt_secret
from .models import Asset, BackupPolicy, StorageRepository
from .restic_manager import generate_resticprofile_yaml, profile_name_for_asset


def generate_agent_bundle(asset: Asset, policy: BackupPolicy | None, repo: StorageRepository | None) -> dict:
    paths = json.loads(policy.backup_paths_json) if policy else ["C:\\Empower\\Projects"]
    excludes = json.loads(policy.exclude_patterns_json) if policy else ["*.tmp", "*.lck"]
    schedule_cron = policy.schedule_cron if policy else "0 2 * * *"
    repo_uri = repo.repo_uri if repo else "rest:http://localhost:8000/gmp-repo"
    profile_name = profile_name_for_asset(asset)

    effective_policy = policy or BackupPolicy(
        asset_id=asset.id,
        repository_id=repo.id if repo else 1,
        name=f"{asset.asset_tag} Standard Restic Policy",
        is_enabled=True,
        execution_mode="ENDPOINT_AGENT",
        schedule_preset="DAILY",
        schedule_cron=schedule_cron,
        backup_paths_json=json.dumps(paths),
        exclude_patterns_json=json.dumps(excludes),
        rpo_hours=24,
        rto_hours=4,
        retention_keep_last=7,
        retention_keep_daily=14,
        retention_keep_weekly=8,
        retention_keep_monthly=12,
        retention_keep_yearly=7,
        vss_enabled=(asset.os_type == "WINDOWS"),
        config_version=1,
    )
    effective_repo = repo or StorageRepository(
        name="Default-GMP-Vault",
        backend_type="RESTIC_REST",
        repo_uri=repo_uri,
        encrypted_password=encrypt_secret("gmp-restic-repo-default-password"),
        encrypted_env_json="",
        immutable_append_only=False,
    )

    resticprofile_yaml = generate_resticprofile_yaml(
        effective_repo,
        asset,
        effective_policy,
        for_gateway=False,
        api_url=PUBLIC_API_URL,
    )

    windows_ps1 = f"""# ==============================================================================
# CFR-App Dynamic GxP Backup Agent for Windows (resticprofile / Restic + VSS)
# Asset Tag : {asset.asset_tag} ({asset.name})
# Profile   : {profile_name}
# GMP Status: {"GMP Regulated" if asset.is_gmp else "Non-GMP"} | Criticality: {asset.criticality}
# ==============================================================================
param(
    [string]$ApiUrl = "{PUBLIC_API_URL}",
    [string]$AgentToken = "{asset.agent_token}",
    [switch]$ForceBackup
)

$ErrorActionPreference = "Stop"
$Headers = @{{ "X-Agent-Token" = $AgentToken }}
$StateDir = "C:\\ProgramData\\CFRApp"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# 1. Poll Central CFR-App Server for dynamic schedule, resticprofile YAML & encrypted credentials
$Config = Invoke-RestMethod -Uri "$ApiUrl/agents/config" -Method Get -Headers $Headers

if (-not $Config.policy_enabled) {{
    Write-Output "[CFR-Agent] Backup policy disabled centrally for $($Config.asset_tag)."
    exit 0
}}

if (-not $ForceBackup -and -not $Config.should_run_now) {{
    Write-Output "[CFR-Agent] Schedule window not active (Cron: $($Config.schedule_cron))."
    exit 0
}}

# 2. Set Restic Repository & Credentials in memory and write local resticprofile config
$env:RESTIC_REPOSITORY = $Config.repository_uri
$env:RESTIC_PASSWORD   = $Config.repository_password
foreach ($kv in $Config.repository_env.PSObject.Properties) {{
    [Environment]::SetEnvironmentVariable($kv.Name, $kv.Value, "Process")
}}

$ProfileFile = Join-Path $StateDir "profiles.yaml"
$PasswordFile = Join-Path $StateDir "repository-password.txt"
Set-Content -Path $PasswordFile -Value $Config.repository_password -NoNewline
if ($Config.resticprofile_yaml) {{
    Set-Content -Path $ProfileFile -Value $Config.resticprofile_yaml
}}

# 3. Run via resticprofile if installed, or fallback to restic.exe with VSS (--use-fs-snapshot)
$StartTime = (Get-Date).ToUniversalTime().ToString("o")
$ResticProfileExe = Get-Command "resticprofile.exe" -ErrorAction SilentlyContinue

if ($ResticProfileExe -and (Test-Path $ProfileFile)) {{
    $Output = & $ResticProfileExe.Source --no-ansi -c $ProfileFile -n "{profile_name}" backup --json 2>&1 | Out-String
}} else {{
    $ArgsList = @("backup", "--json", "--tag", "asset:$($Config.asset_tag)", "--tag", "gmp:$($Config.is_gmp)")
    if ($Config.vss_enabled) {{ $ArgsList += "--use-fs-snapshot" }}
    foreach ($ex in $Config.exclude_patterns) {{ $ArgsList += "--exclude=$ex" }}
    foreach ($p in $Config.backup_paths) {{ $ArgsList += $p }}
    $Output = & "C:\\Program Files\\Restic\\restic.exe" @ArgsList 2>&1 | Out-String
}}

$SummaryLine = ($Output -split "`n" | Where-Object {{ $_ -match '"message_type":"summary"' }} | Select-Object -Last 1)
$Summary = if ($SummaryLine) {{ $SummaryLine | ConvertFrom-Json }} else {{ $null }}

$Payload = @{{
    status                = "COMPLETED"
    started_at            = $StartTime
    completed_at          = (Get-Date).ToUniversalTime().ToString("o")
    snapshot_id           = if ($Summary) {{ $Summary.snapshot_id }} else {{ "unknown" }}
    files_new             = if ($Summary) {{ $Summary.files_new }} else {{ 0 }}
    files_changed         = if ($Summary) {{ $Summary.files_changed }} else {{ 0 }}
    files_unmodified      = if ($Summary) {{ $Summary.files_unmodified }} else {{ 0 }}
    bytes_added           = if ($Summary) {{ $Summary.data_added }} else {{ 0 }}
    total_bytes_processed = if ($Summary) {{ $Summary.total_bytes_processed }} else {{ 0 }}
    log_output            = $Output
}} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "$ApiUrl/agents/report" -Method Post -Headers $Headers -ContentType "application/json" -Body $Payload
"""

    unix_sh = f"""#!/usr/bin/env bash
# ==============================================================================
# CFR-App Dynamic GxP Backup Agent for Linux / macOS (resticprofile + Restic)
# Asset Tag : {asset.asset_tag} ({asset.name})
# Profile   : {profile_name}
# GMP Status: {"GMP Regulated" if asset.is_gmp else "Non-GMP"} | Criticality: {asset.criticality}
# ==============================================================================
set -euo pipefail

API_URL="${{CFR_API_URL:-{PUBLIC_API_URL}}}"
AGENT_TOKEN="${{CFR_AGENT_TOKEN:-{asset.agent_token}}}"
FORCE_RUN="${{1:-false}}"
STATE_DIR="/etc/cfr-agent"
mkdir -p "${{STATE_DIR}}" 2>/dev/null || STATE_DIR="/tmp/cfr-agent"
mkdir -p "${{STATE_DIR}}"

CONFIG_JSON=$(curl -fsSL -H "X-Agent-Token: ${{AGENT_TOKEN}}" "${{API_URL}}/agents/config")

SHOULD_RUN=$(echo "${{CONFIG_JSON}}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('policy_enabled') and d.get('should_run_now'))")
if [[ "${{FORCE_RUN}}" != "--force" && "${{SHOULD_RUN}}" != "True" ]]; then
  exit 0
fi

eval "$(echo "${{CONFIG_JSON}}" | python3 -c '
import sys, json, shlex
cfg = json.load(sys.stdin)
print(f"export RESTIC_REPOSITORY={{shlex.quote(cfg[\\"repository_uri\\"])}}")
print(f"export RESTIC_PASSWORD={{shlex.quote(cfg[\\"repository_password\\"])}}")
for k, v in (cfg.get("repository_env") or {{}}).items():
    print(f"export {{k}}={{shlex.quote(str(v))}}")
')"

# Materialize central resticprofile YAML & password file
PROFILE_FILE="${{STATE_DIR}}/profiles.yaml"
KEY_FILE="/etc/cfr-agent/{profile_name}.key"
if [[ -w "/etc/cfr-agent" ]]; then
  printf "%s" "${{RESTIC_PASSWORD}}" > "${{KEY_FILE}}"
  chmod 0600 "${{KEY_FILE}}"
fi
curl -fsSL -H "X-Agent-Token: ${{AGENT_TOKEN}}" "${{API_URL}}/agents/profile.yaml" > "${{PROFILE_FILE}}" 2>/dev/null || true

PATHS_ARGS=$(echo "${{CONFIG_JSON}}" | python3 -c "import sys,json,shlex; print(' '.join(shlex.quote(p) for p in json.load(sys.stdin)['backup_paths']))")
EXCLUDE_ARGS=$(echo "${{CONFIG_JSON}}" | python3 -c "import sys,json,shlex; print(' '.join('--exclude=' + shlex.quote(x) for x in json.load(sys.stdin).get('exclude_patterns', [])))")

START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUT_FILE=$(mktemp)

if command -v resticprofile >/dev/null 2>&1 && [[ -s "${{PROFILE_FILE}}" && -f "${{KEY_FILE}}" ]]; then
  if resticprofile --no-ansi -c "${{PROFILE_FILE}}" -n "{profile_name}" backup --json > "${{OUT_FILE}}" 2>&1; then
    STATUS="COMPLETED"
  else
    STATUS="FAILED"
  fi
elif eval "restic backup --json --tag asset:{asset.asset_tag} ${{EXCLUDE_ARGS}} ${{PATHS_ARGS}}" > "${{OUT_FILE}}" 2>&1; then
  STATUS="COMPLETED"
else
  STATUS="FAILED"
fi

END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
python3 - "${{OUT_FILE}}" "${{STATUS}}" "${{START_TIME}}" "${{END_TIME}}" "${{API_URL}}" "${{AGENT_TOKEN}}" << 'PYEOF'
import sys, json, urllib.request
out_f, status, st, et, url, tok = sys.argv[1:7]
raw = open(out_f).read()
summary = {{}}
for line in raw.splitlines():
    if '"message_type":"summary"' in line:
        try: summary = json.loads(line)
        except Exception: pass
payload = {{
    "status": status, "started_at": st, "completed_at": et,
    "snapshot_id": summary.get("snapshot_id"),
    "files_new": summary.get("files_new", 0),
    "files_changed": summary.get("files_changed", 0),
    "files_unmodified": summary.get("files_unmodified", 0),
    "bytes_added": summary.get("data_added", 0),
    "total_bytes_processed": summary.get("total_bytes_processed", 0),
    "log_output": raw[-8000:]
}}
req = urllib.request.Request(f"{{url}}/agents/report", data=json.dumps(payload).encode(), headers={{"Content-Type": "application/json", "X-Agent-Token": tok}}, method="POST")
urllib.request.urlopen(req, timeout=15)
PYEOF
rm -f "${{OUT_FILE}}"
"""

    agentless_guide = f"""# ==============================================================================
# Agentless / Legacy Equipment Gateway Configuration for {asset.asset_tag}
# Equipment: {asset.vendor} {asset.model} ({asset.os_type})
# resticprofile Profile Name: {profile_name}
# ==============================================================================

# Option 1: Read-Only SMB/CIFS Mount on CFR-App Gateway Host
# 1. Create a read-only local user 'cfr_backup_svc' on {asset.hostname_or_ip}
# 2. Mount share read-only into /app/data/landing_zones/{asset.asset_tag}:
sudo mkdir -p /app/data/landing_zones/{asset.asset_tag}
sudo mount -t cifs //{asset.hostname_or_ip}/InstrumentData /app/data/landing_zones/{asset.asset_tag} \\
  -o ro,vers=2.1,username=cfr_backup_svc,password=YOUR_READONLY_PASS

# Option 2: SFTP / Rsync Push to CFR-App Landing Zone
# Configure the instrument's automated batch export to write to:
#   Host: cfr-gateway.local
#   Path: /app/data/landing_zones/{asset.asset_tag}
#
# The CFR-App Central Gateway automatically generates /app/data/profiles/{profile_name}.yaml
# and executes:
#   resticprofile --no-ansi -c /app/data/profiles/{profile_name}.yaml -n {profile_name} backup --json
# on schedule ({schedule_cron}) targeting repository: {repo_uri}
"""

    return {
        "asset_tag": asset.asset_tag,
        "asset_name": asset.name,
        "os_type": asset.os_type,
        "agent_token": asset.agent_token,
        "schedule_cron": schedule_cron,
        "backup_paths": paths,
        "exclude_patterns": excludes,
        "repository_uri": repo_uri,
        "resticprofile_name": profile_name,
        "resticprofile_yaml": resticprofile_yaml,
        "windows_powershell_script": windows_ps1,
        "unix_bash_script": unix_sh,
        "agentless_setup_commands": agentless_guide,
    }
