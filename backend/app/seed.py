from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from sqlalchemy.orm import Session
from .audit import record_audit_event
from .auth import hash_password
from .compliance import compute_next_run
from .config import DATA_DIR, RESTIC_DEFAULT_REPO_PASSWORD, RESTIC_REST_SERVER_URL, encrypt_env_dict, encrypt_secret
from .models import Asset, BackupJob, BackupPolicy, RestoreDrill, SOPDocument, SnapshotRecord, StorageRepository, User
from .restic_manager import execute_restore_and_verify, init_repository, list_snapshot_files, run_gateway_backup


def _create_sample_instrument_files() -> dict[str, str]:
    base = DATA_DIR / "sample_instruments"
    paths = {}

    hplc_dir = base / "HPLC-QC-001"
    hplc_dir.mkdir(parents=True, exist_ok=True)
    (hplc_dir / "Empower3_Batch_20261109_mAb_Purity.arw").write_text(
        "WATERS_EMPOWER3_RAW_CHROMATOGRAM\nSampleSet: mAb_Lot_2026_094\nDetector: PDA_280nm\nPeak_1_Retention_Min: 4.812\nPurity_Area_Pct: 99.42\n"
    )
    (hplc_dir / "SystemSuitability_USP_Method.meth").write_text(
        "Method: USP_Monoclonal_IgG1_SEC_HPLC\nFlowRate_mL_min: 0.50\nColumnTemp_C: 25.0\nInjectionVolume_uL: 10.0\n"
    )
    paths["HPLC-QC-001"] = str(hplc_dir)

    ms_dir = base / "MS-BIO-002"
    ms_dir.mkdir(parents=True, exist_ok=True)
    (ms_dir / "Orbitrap_PeptideMap_Run08.raw.manifest").write_text(
        "THERMO_ORBITRAP_EXPLORIS_480\nResolution: 120000\nMassRange_m_z: 150-2000\nSequenceCoverage_Pct: 98.7\n"
    )
    paths["MS-BIO-002"] = str(ms_dir)

    bio_dir = DATA_DIR / "landing_zones" / "BIO-PLC-003"
    bio_dir.mkdir(parents=True, exist_ok=True)
    (bio_dir / "Biostat_STR200L_Batch_B26_Telemetry.csv").write_text(
        "timestamp_utc,temp_c,ph,dissolved_o2_pct,agitation_rpm\n"
        "2026-11-09T01:00:00Z,37.01,7.02,45.2,180\n"
        "2026-11-09T02:00:00Z,37.00,7.01,44.8,182\n"
    )
    paths["BIO-PLC-003"] = str(bio_dir)

    seq_dir = base / "SEQ-GEN-004"
    seq_dir.mkdir(parents=True, exist_ok=True)
    (seq_dir / "NovaSeqX_RunInfo.xml").write_text(
        "<RunInfo><Run Id='261109_LH00142_0045' Flowcell='22H7GMLT4'><Reads>150bp_PairedEnd</Reads><Q30_Pct>94.6</Q30_Pct></Run></RunInfo>\n"
    )
    paths["SEQ-GEN-004"] = str(seq_dir)

    flow_dir = base / "FLOW-RD-005"
    flow_dir.mkdir(parents=True, exist_ok=True)
    (flow_dir / "CAR_T_Phenotyping_Panel.fcs.txt").write_text(
        "FCS3.1_HEADER\nCytometer: BD FACSAria Fusion\nEvents: 250000\nParameters: FSC-A,SSC-A,CD3-FITC,CD4-PE,CD8-APC\n"
    )
    paths["FLOW-RD-005"] = str(flow_dir)

    return paths


def seed_initial_data(db: Session):
    if db.query(User).count() > 0:
        return

    sample_dirs = _create_sample_instrument_files()
    now = datetime.now(timezone.utc)

    # 1. Seed Users across all 4 RBAC roles
    default_pw_hash = hash_password("gmp-password-123")
    users = [
        User(
            username="admin",
            full_name="Dr. Elena Vance",
            email="elena.vance@biopharma-gmp.org",
            role="Admin",
            password_hash=default_pw_hash,
        ),
        User(
            username="qa_director",
            full_name="Marcus Chen",
            email="marcus.chen@biopharma-gmp.org",
            role="QA_Compliance",
            password_hash=default_pw_hash,
        ),
        User(
            username="lab_eng",
            full_name="Sarah Jenkins",
            email="sarah.jenkins@biopharma-gmp.org",
            role="Lab_Engineer",
            password_hash=default_pw_hash,
        ),
        User(
            username="fda_auditor",
            full_name="Inspector David Miller",
            email="david.miller@regulatory-audit.org",
            role="Auditor",
            password_hash=default_pw_hash,
        ),
    ]
    db.add_all(users)
    db.commit()

    # 2. Seed Approved Backup & Restore SOPs
    sop_gmp = SOPDocument(
        sop_code="SOP-CSV-008",
        title="GMP Computerized Laboratory & Bioprocess Systems Backup and Restore Verification",
        version="3.0",
        status="APPROVED",
        target_rpo_hours=24,
        target_rto_hours=4,
        drill_interval_days=90,
        content_markdown=(
            "### 1. Purpose\nDefines mandatory encrypted Restic backup schedules and periodic restore verification drills "
            "for all Critical and GMP-regulated laboratory instruments in compliance with FDA 21 CFR Part 11 and EU GMP Annex 11 §7.1.\n\n"
            "### 2. Mandatory Requirements\n"
            "- **RPO**: Maximum 24 hours between verified Restic snapshots.\n"
            "- **RTO**: Maximum 4 hours (240 minutes) from restore initiation to verified SHA-256 file integrity.\n"
            "- **Immutability**: Repositories storing GMP data should enable `--append-only` or S3 Object Lock.\n"
            "- **Verification**: Restore drills must be executed every 90 days and electronically signed by QA."
        ),
        checklist_json=json.dumps(
            [
                "Verify target Restic snapshot ID and timestamp fall within RPO window",
                "Execute restic restore into isolated verification staging directory",
                "Compare SHA-256 cryptographic manifest of restored raw instrument files",
                "Confirm Actual RTO duration is within Target RTO (<= 240 minutes)",
                "Obtain Quality Assurance (QA) 21 CFR Part 11 Electronic Signature sign-off",
            ]
        ),
        approved_by="Marcus Chen (qa_director)",
        approved_at=now,
    )
    sop_rd = SOPDocument(
        sop_code="SOP-IT-014",
        title="Non-GMP Discovery & R&D Instrument Data Protection Procedure",
        version="1.2",
        status="APPROVED",
        target_rpo_hours=48,
        target_rto_hours=12,
        drill_interval_days=180,
        content_markdown=(
            "### 1. Purpose\nStandardizes Restic backups for Non-GMP R&D workstations and high-throughput discovery instruments.\n\n"
            "### 2. Requirements\n- Daily or Weekly Restic snapshots with 6-month retention."
        ),
        checklist_json=json.dumps(
            [
                "Restore snapshot to staging directory",
                "Confirm file readability and SHA-256 checksums",
            ]
        ),
        approved_by="Dr. Elena Vance (admin)",
        approved_at=now,
    )
    db.add_all([sop_gmp, sop_rd])
    db.commit()
    db.refresh(sop_gmp)
    db.refresh(sop_rd)

    # 3. Seed Multi-Backend Storage Repositories
    local_repo_path = str((DATA_DIR / "repos" / "gmp_primary_vault").resolve())
    repo_local = StorageRepository(
        name="OnPrem-GMP-Primary-Vault",
        backend_type="LOCAL_NAS",
        repo_uri=local_repo_path,
        encrypted_password=encrypt_secret(RESTIC_DEFAULT_REPO_PASSWORD),
        encrypted_env_json=encrypt_env_dict({}),
        immutable_append_only=False,
        is_initialized=False,
        status="UNINITIALIZED",
        notes="Primary high-speed local/NAS Restic vault for immediate lab recovery and verification drills",
    )
    repo_rest = StorageRepository(
        name="Restic-REST-AppendOnly-Server",
        backend_type="RESTIC_REST",
        repo_uri=f"rest:{RESTIC_REST_SERVER_URL}/gmp-immutable",
        encrypted_password=encrypt_secret(RESTIC_DEFAULT_REPO_PASSWORD),
        encrypted_env_json=encrypt_env_dict({}),
        immutable_append_only=True,
        is_initialized=False,
        status="HEALTHY",
        notes="Dockerized restic/rest-server running with --append-only flag for ransomware-proof GMP snapshots",
    )
    repo_minio = StorageRepository(
        name="MinIO-OnPrem-S3-ObjectStore",
        backend_type="MINIO",
        repo_uri="s3:http://minio:9000/gmp-restic-bucket/instruments",
        encrypted_password=encrypt_secret(RESTIC_DEFAULT_REPO_PASSWORD),
        encrypted_env_json=encrypt_env_dict(
            {
                "AWS_ACCESS_KEY_ID": "minioadmin",
                "AWS_SECRET_ACCESS_KEY": "minioadmin_secret_change_me",
                "AWS_DEFAULT_REGION": "us-east-1",
            }
        ),
        immutable_append_only=True,
        is_initialized=False,
        status="HEALTHY",
        notes="Self-hosted S3-compatible MinIO object storage bundled in Docker Compose",
    )
    repo_aws = StorageRepository(
        name="AWS-S3-Offsite-ComplianceLock",
        backend_type="S3_COMPATIBLE",
        repo_uri="s3:https://s3.us-east-1.amazonaws.com/biopharma-cfr11-dr-archive/restic",
        encrypted_password=encrypt_secret(RESTIC_DEFAULT_REPO_PASSWORD),
        encrypted_env_json=encrypt_env_dict(
            {
                "AWS_ACCESS_KEY_ID": "AKIA_CONFIGURE_IN_SETTINGS",
                "AWS_SECRET_ACCESS_KEY": "CONFIGURE_SECRET_IN_SETTINGS",
                "AWS_DEFAULT_REGION": "us-east-1",
            }
        ),
        immutable_append_only=True,
        is_initialized=False,
        status="UNINITIALIZED",
        notes="Off-site 3-2-1 disaster recovery tier using AWS S3 Object Lock (Compliance WORM Mode)",
    )
    db.add_all([repo_local, repo_rest, repo_minio, repo_aws])
    db.commit()
    db.refresh(repo_local)

    # Initialize the real local Restic repository so live snapshots & restores work immediately
    ok, msg = init_repository(repo_local)
    repo_local.is_initialized = ok
    repo_local.status = "HEALTHY" if ok else "ERROR"
    repo_local.last_check_output = msg
    repo_local.last_checked_at = now
    db.commit()

    # 4. Seed Life Science Assets
    assets_data = [
        {
            "asset_tag": "HPLC-QC-001",
            "name": "Waters Acquity UPLC H-Class (Empower 3 Node)",
            "category": "Chromatography (HPLC/UPLC)",
            "vendor": "Waters Corporation",
            "model": "Acquity UPLC H-Class Bio",
            "serial_number": "WTR-UPLC-994821",
            "software_version": "Empower 3 FR5",
            "location": "Bldg A - QC Analytical Lab 204",
            "hostname_or_ip": "10.20.14.101",
            "os_type": "WINDOWS",
            "is_gmp": True,
            "criticality": "CRITICAL",
            "system_owner": "Dr. Rachel Kim (QC Release)",
            "qa_owner": "Marcus Chen (QA Compliance)",
            "sop_id": sop_gmp.id,
            "notes": "Commercial batch release purity testing; uses Windows VSS (--use-fs-snapshot) for open Empower project files.",
        },
        {
            "asset_tag": "MS-BIO-002",
            "name": "Thermo Orbitrap Exploris 480 LC-MS/MS",
            "category": "Mass Spectrometry",
            "vendor": "Thermo Fisher Scientific",
            "model": "Orbitrap Exploris 480",
            "serial_number": "SN-ORB480-11209",
            "software_version": "Chromeleon 7.3 / Xcalibur 4.6",
            "location": "Bldg A - Biologics Characterization Lab 210",
            "hostname_or_ip": "10.20.14.102",
            "os_type": "WINDOWS",
            "is_gmp": True,
            "criticality": "CRITICAL",
            "system_owner": "Dr. Viktor Patel (Analytical Dev)",
            "qa_owner": "Marcus Chen (QA Compliance)",
            "sop_id": sop_gmp.id,
            "notes": "High-resolution peptide mapping and PTM characterization for GMP stability studies.",
        },
        {
            "asset_tag": "BIO-PLC-003",
            "name": "Sartorius Biostat STR 200L Single-Use Bioreactor",
            "category": "Bioreactor / Fermenter",
            "vendor": "Sartorius Stedim",
            "model": "Biostat STR 200L DCU-4",
            "serial_number": "SRT-STR200-55812",
            "software_version": "BioPAT MFCS 4.1 (Embedded PLC)",
            "location": "Bldg B - GMP Upstream Suite 102",
            "hostname_or_ip": "10.30.50.18",
            "os_type": "AGENTLESS_SMB",
            "is_gmp": True,
            "criticality": "CRITICAL",
            "system_owner": "Carlos Mendez (Upstream Mfg)",
            "qa_owner": "Marcus Chen (QA Compliance)",
            "sop_id": sop_gmp.id,
            "notes": "Closed PLC controller where Restic cannot be installed; backed up via CFR-App Central Gateway over read-only SMB/CIFS.",
        },
        {
            "asset_tag": "SEQ-GEN-004",
            "name": "Illumina NovaSeq X Plus NGS Sequencer",
            "category": "Genomics / NGS Sequencer",
            "vendor": "Illumina",
            "model": "NovaSeq X Plus",
            "serial_number": "LH00142",
            "software_version": "NovaSeq X Control Software v1.2",
            "location": "Bldg C - Cell & Gene Therapy QC Lab 305",
            "hostname_or_ip": "10.20.18.44",
            "os_type": "LINUX",
            "is_gmp": True,
            "criticality": "CRITICAL",
            "system_owner": "Dr. Hannah Lin (Genomic QC)",
            "qa_owner": "Marcus Chen (QA Compliance)",
            "sop_id": sop_gmp.id,
            "notes": "Viral vector adventitious agent sequencing. Needs backup policy assigned to clear compliance alert.",
        },
        {
            "asset_tag": "FLOW-RD-005",
            "name": "BD FACSAria Fusion Cell Sorter Workstation",
            "category": "Flow Cytometry",
            "vendor": "BD Biosciences",
            "model": "FACSAria Fusion",
            "serial_number": "BD-FUS-77319",
            "software_version": "FACSDiva v9 / FlowJo v10.10",
            "location": "Bldg D - Discovery Immunology Lab 115",
            "hostname_or_ip": "10.40.12.88",
            "os_type": "MACOS",
            "is_gmp": False,
            "criticality": "MAJOR",
            "system_owner": "Dr. Liam O'Connor (Immunology R&D)",
            "qa_owner": "N/A (Non-GMP)",
            "sop_id": sop_rd.id,
            "notes": "macOS analysis workstation running launchd Restic daemon with Full Disk Access.",
        },
        {
            "asset_tag": "PH-BENCH-006",
            "name": "Mettler Toledo SevenExcellence pH/Conductivity Meter",
            "category": "Benchtop Meter / Balance",
            "vendor": "Mettler Toledo",
            "model": "S470-Std-K",
            "serial_number": "MT-S470-30912",
            "software_version": "Firmware 4.2",
            "location": "Bldg D - Media Prep Room 104",
            "hostname_or_ip": "N/A (Standalone)",
            "os_type": "AIRGAPPED_USB",
            "is_gmp": False,
            "criticality": "MINOR",
            "system_owner": "Lab Operations",
            "qa_owner": "N/A (Non-GMP)",
            "sop_id": None,
            "notes": "Stateless minor R&D benchtop meter; direct print to lab notebook, exempt from automated Restic backup.",
        },
    ]

    created_assets: dict[str, Asset] = {}
    for ad in assets_data:
        token = f"cfr_agt_{ad['asset_tag'].lower().replace('-', '_')}_{secrets.token_hex(6)}"
        asset = Asset(**ad, agent_token=token, agent_last_seen_at=now)
        db.add(asset)
        db.commit()
        db.refresh(asset)
        created_assets[asset.asset_tag] = asset

    # 5. Create Backup Policies & Run Real Restic Backups for HPLC-QC-001, MS-BIO-002, BIO-PLC-003, FLOW-RD-005
    policy_configs = [
        ("HPLC-QC-001", "EVERY_4_HOURS", "0 */4 * * *", "ENDPOINT_AGENT", 4, 2, True),
        ("MS-BIO-002", "DAILY", "0 2 * * *", "ENDPOINT_AGENT", 24, 4, True),
        ("BIO-PLC-003", "HOURLY", "0 * * * *", "CENTRAL_GATEWAY", 4, 2, False),
        ("FLOW-RD-005", "DAILY", "0 3 * * *", "ENDPOINT_AGENT", 48, 12, False),
    ]

    for tag, preset, cron_expr, exec_mode, rpo_h, rto_h, vss in policy_configs:
        asset = created_assets[tag]
        pol = BackupPolicy(
            asset_id=asset.id,
            repository_id=repo_local.id,
            name=f"{tag} Standard {preset.replace('_', ' ').title()} Restic Policy",
            is_enabled=True,
            execution_mode=exec_mode,
            schedule_preset=preset,
            schedule_cron=cron_expr,
            backup_paths_json=json.dumps([sample_dirs[tag]]),
            exclude_patterns_json=json.dumps(["*.tmp", "*.lck", "*~"]),
            rpo_hours=rpo_h,
            rto_hours=rto_h,
            retention_keep_last=10,
            retention_keep_daily=14,
            retention_keep_weekly=8,
            retention_keep_monthly=12,
            retention_keep_yearly=7,
            vss_enabled=vss,
            gateway_share_uri=f"//{asset.hostname_or_ip}/InstrumentData" if exec_mode == "CENTRAL_GATEWAY" else None,
            config_version=1,
            next_run_at=compute_next_run(cron_expr, now),
        )
        db.add(pol)
        db.commit()
        db.refresh(pol)

        # Execute a real Restic backup so real snapshots exist on disk
        res = run_gateway_backup(repo_local, asset, pol)
        done_time = datetime.now(timezone.utc)
        job = BackupJob(
            policy_id=pol.id,
            asset_id=asset.id,
            repository_id=repo_local.id,
            triggered_by="INITIAL_QUALIFICATION_SEED",
            execution_mode=exec_mode,
            status=res["status"],
            started_at=now,
            completed_at=done_time,
            duration_seconds=res["duration_seconds"],
            snapshot_id=res["snapshot_id"],
            files_new=res["files_new"],
            files_changed=res["files_changed"],
            files_unmodified=res["files_unmodified"],
            bytes_added=res["bytes_added"],
            total_bytes_processed=res["total_bytes_processed"],
            log_output=res["log_output"],
            error_message=res["error_message"],
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        if res["status"] == "COMPLETED" and res.get("snapshot_id"):
            pol.last_run_at = done_time
            files = list_snapshot_files(repo_local, res["snapshot_id"])
            file_count = sum(1 for f in files if f.get("type") == "file") or 1
            snap = SnapshotRecord(
                snapshot_id=res["snapshot_id"],
                short_id=res["snapshot_id"][:8],
                asset_id=asset.id,
                repository_id=repo_local.id,
                job_id=job.id,
                hostname=asset.hostname_or_ip,
                paths_json=pol.backup_paths_json,
                tags_json=json.dumps([f"asset:{asset.asset_tag}", f"gmp:{asset.is_gmp}", f"criticality:{asset.criticality}"]),
                created_at=done_time,
                size_bytes=res["total_bytes_processed"],
                file_count=file_count,
                is_verified=(tag in ("HPLC-QC-001", "BIO-PLC-003")),
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)

            # Execute real restore verification drills for the 3 backed-up Critical GMP assets
            if tag in ("HPLC-QC-001", "BIO-PLC-003", "MS-BIO-002"):
                target_dir = str(DATA_DIR / "restores" / f"seed_drill_{tag}_{snap.short_id}")
                r_res = execute_restore_and_verify(repo_local, snap.snapshot_id, target_dir)
                qa_approved = tag in ("HPLC-QC-001", "BIO-PLC-003")
                drill = RestoreDrill(
                    asset_id=asset.id,
                    repository_id=repo_local.id,
                    snapshot_id=snap.snapshot_id,
                    sop_id=sop_gmp.id,
                    restore_type="SOP_DRILL",
                    target_path=target_dir,
                    status="QA_APPROVED" if qa_approved else "COMPLETED_PENDING_QA",
                    started_at=done_time,
                    completed_at=done_time,
                    actual_rto_minutes=r_res["actual_rto_minutes"],
                    target_rto_minutes=float(rto_h * 60),
                    restored_file_count=r_res["restored_file_count"],
                    restored_bytes=r_res["restored_bytes"],
                    checksum_verified=r_res["success"],
                    sha256_manifest_json=json.dumps(r_res["sha256_manifest"]),
                    checklist_results_json=json.dumps(
                        [
                            {"step": "1. Locate snapshot in Restic repository", "passed": True},
                            {"step": "2. Execute restic restore to isolated verification target", "passed": True},
                            {"step": "3. Compute & verify SHA-256 manifest of restored files", "passed": True},
                            {"step": "4. Confirm Actual RTO <= Target RTO", "passed": True},
                        ]
                    ),
                    executed_by="Sarah Jenkins (lab_eng)",
                    qa_signed_by="Marcus Chen (qa_director)" if qa_approved else None,
                    qa_signed_at=done_time if qa_approved else None,
                    qa_signature_meaning="Verified" if qa_approved else None,
                    notes=(
                        "Quarterly SOP-CSV-008 restore verification drill passed with 100% SHA-256 match."
                        if qa_approved
                        else "Restore drill completed; awaiting QA Director 21 CFR Part 11 Electronic Signature."
                    ),
                )
                db.add(drill)
                db.commit()

    # 6. Write initial hash-chained 21 CFR Part 11 Audit Trail entries
    record_audit_event(
        db,
        actor_username="admin",
        actor_role="Admin",
        action="SYSTEM_INITIALIZED",
        entity_type="System",
        entity_id="CFR-APP-V1",
        summary="Initialized Life Science Asset & GxP Restic Backup Management System with 21 CFR Part 11 hash-chained audit trail",
        reason="Initial Computer System Validation (CSV) IQ/OQ baseline qualification",
        signature_meaning="Approved",
        signature_verified=True,
    )
    record_audit_event(
        db,
        actor_username="qa_director",
        actor_role="QA_Compliance",
        action="SOP_APPROVED",
        entity_type="SOPDocument",
        entity_id="SOP-CSV-008",
        summary="QA approved SOP-CSV-008 v3.0 (GMP Computerized Laboratory & Bioprocess Systems Backup and Restore Verification)",
        reason="Annual QMS SOP review and approval",
        signature_meaning="Approved",
        signature_verified=True,
    )
