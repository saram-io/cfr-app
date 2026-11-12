import os
from pathlib import Path
import shutil
import tempfile

# Point DATA_DIR and DATABASE_URL to an isolated temporary directory for tests
TEST_TMP_DIR = Path(tempfile.mkdtemp(prefix="cfr_app_test_"))
os.environ["DATA_DIR"] = str(TEST_TMP_DIR)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_TMP_DIR / 'test_cfr.db'}"

from fastapi.testclient import TestClient
from app.main import app


def test_end_to_end_gmp_asset_restic_backup_restore_and_audit_chain():
    with TestClient(app) as client:
        # 1. Health check
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        # 2. Login as Lab Engineer and QA Director
        login_eng = client.post("/api/v1/auth/login", json={"username": "lab_eng", "password": "gmp-password-123"})
        assert login_eng.status_code == 200
        eng_token = login_eng.json()["access_token"]
        eng_headers = {"Authorization": f"Bearer {eng_token}"}

        login_qa = client.post("/api/v1/auth/login", json={"username": "qa_director", "password": "gmp-password-123"})
        assert login_qa.status_code == 200
        qa_token = login_qa.json()["access_token"]
        qa_headers = {"Authorization": f"Bearer {qa_token}"}

        # 3. Verify Dashboard & Seeded Assets
        dash = client.get("/api/v1/dashboard/summary", headers=eng_headers).json()
        assert dash["kpis"]["total_assets"] >= 6
        assert dash["kpis"]["gmp_assets"] >= 4
        assert dash["kpis"]["total_snapshots"] >= 4

        assets = client.get("/api/v1/assets", headers=eng_headers).json()
        by_tag = {a["asset_tag"]: a for a in assets}

        # HPLC-QC-001 has policy, SOP, recent Restic snapshot, and QA-signed restore drill -> COMPLIANT
        assert by_tag["HPLC-QC-001"]["compliance"]["overall_status"] == "COMPLIANT"
        # MS-BIO-002 has drill pending QA signature -> AT_RISK
        assert by_tag["MS-BIO-002"]["compliance"]["overall_status"] == "AT_RISK"
        # SEQ-GEN-004 is Critical GMP without backup policy -> NON_COMPLIANT
        seq_asset = by_tag["SEQ-GEN-004"]
        assert seq_asset["compliance"]["overall_status"] == "NON_COMPLIANT"
        # PH-BENCH-006 is Minor Non-GMP -> EXEMPT
        assert by_tag["PH-BENCH-006"]["compliance"]["overall_status"] == "EXEMPT"

        # 4. Verify 21 CFR Part 11 Electronic Signature enforcement when updating a GMP asset
        bad_update = client.put(
            f"/api/v1/assets/{seq_asset['id']}",
            headers=eng_headers,
            json={"location": "Bldg C - Suite 999"},
        )
        assert bad_update.status_code == 400  # E-Signature required

        good_update = client.put(
            f"/api/v1/assets/{seq_asset['id']}",
            headers=eng_headers,
            json={
                "location": "Bldg C - Validated NGS Suite 305B",
                "esignature": {
                    "username": "lab_eng",
                    "password": "gmp-password-123",
                    "meaning": "Authored",
                    "reason": "Updated room number per Change Control CC-2026-041",
                },
            },
        )
        assert good_update.status_code == 200
        assert good_update.json()["location"] == "Bldg C - Validated NGS Suite 305B"

        # 5. Create Backup Policy for SEQ-GEN-004 and execute real Restic backup
        repos = client.get("/api/v1/storage", headers=eng_headers).json()
        primary_repo = next(r for r in repos if r["name"] == "OnPrem-GMP-Primary-Vault")

        pol_resp = client.post(
            "/api/v1/policies",
            headers=eng_headers,
            json={
                "asset_id": seq_asset["id"],
                "repository_id": primary_repo["id"],
                "name": "SEQ-GEN-004 Daily Restic Policy",
                "is_enabled": True,
                "execution_mode": "ENDPOINT_AGENT",
                "schedule_preset": "DAILY",
                "schedule_cron": "0 1 * * *",
                "backup_paths": [str(TEST_TMP_DIR / "sample_instruments" / "SEQ-GEN-004")],
                "exclude_patterns": ["*.tmp"],
                "rpo_hours": 24,
                "rto_hours": 4,
            },
        )
        assert pol_resp.status_code == 200
        policy_id = pol_resp.json()["id"]

        run_resp = client.post(f"/api/v1/policies/{policy_id}/run-now", headers=eng_headers)
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "COMPLETED"
        assert run_data["snapshot_id"]

        # 6. Inspect files inside the newly created Restic snapshot
        files_resp = client.get(
            f"/api/v1/backups/snapshots/{run_data['snapshot_id']}/files",
            headers=eng_headers,
        )
        assert files_resp.status_code == 200
        assert len(files_resp.json()["files"]) >= 1

        # 7. Execute SOP Restore Verification Drill and sign off with QA Electronic Signature
        restore_resp = client.post(
            "/api/v1/restores/execute",
            headers=eng_headers,
            json={
                "asset_id": seq_asset["id"],
                "snapshot_id": run_data["snapshot_id"],
                "restore_type": "SOP_DRILL",
                "notes": "Quarterly NGS restore verification test",
            },
        )
        assert restore_resp.status_code == 201
        drill_data = restore_resp.json()
        assert drill_data["checksum_verified"] is True
        assert drill_data["restored_file_count"] >= 1
        assert len(drill_data["sha256_manifest"]) >= 1
        assert drill_data["status"] == "COMPLETED_PENDING_QA"

        sign_resp = client.post(
            f"/api/v1/restores/{drill_data['id']}/qa-signoff",
            headers=qa_headers,
            json={
                "notes": "SHA-256 manifest and RTO verified against SOP-CSV-008",
                "esignature": {
                    "username": "qa_director",
                    "password": "gmp-password-123",
                    "meaning": "Approved",
                    "reason": "Quarterly restore verification passed all SOP-CSV-008 criteria",
                },
            },
        )
        assert sign_resp.status_code == 200
        assert sign_resp.json()["status"] == "QA_APPROVED"

        # Confirm SEQ-GEN-004 is now 100% COMPLIANT
        seq_after = client.get(f"/api/v1/assets/{seq_asset['id']}", headers=eng_headers).json()
        assert seq_after["compliance"]["overall_status"] == "COMPLIANT"

        # 8. Test Endpoint Agent dynamic config polling & script bundle generation
        agent_cfg = client.get(
            "/api/v1/agents/config",
            headers={"X-Agent-Token": seq_after["agent_token"]},
        )
        assert agent_cfg.status_code == 200
        assert agent_cfg.json()["schedule_cron"] == "0 2 * * *"

        # Update schedule to CUSTOM (15 3 * * *) with E-Signature and confirm agent immediately receives updated cron
        upd_pol = client.post(
            "/api/v1/policies",
            headers=eng_headers,
            json={
                "asset_id": seq_asset["id"],
                "repository_id": primary_repo["id"],
                "name": "SEQ-GEN-004 Custom Restic Policy",
                "is_enabled": True,
                "execution_mode": "ENDPOINT_AGENT",
                "schedule_preset": "CUSTOM",
                "schedule_cron": "15 3 * * *",
                "backup_paths": [str(TEST_TMP_DIR / "sample_instruments" / "SEQ-GEN-004")],
                "exclude_patterns": ["*.tmp"],
                "rpo_hours": 24,
                "rto_hours": 4,
                "esignature": {
                    "username": "lab_eng",
                    "password": "gmp-password-123",
                    "meaning": "Approved",
                    "reason": "Adjusted backup window to 03:15 UTC after sequencing run completion",
                },
            },
        )
        assert upd_pol.status_code == 200
        agent_cfg2 = client.get(
            "/api/v1/agents/config",
            headers={"X-Agent-Token": seq_after["agent_token"]},
        )
        assert agent_cfg2.json()["schedule_cron"] == "15 3 * * *"
        assert agent_cfg2.json()["config_version"] == 2

        bundle = client.get(f"/api/v1/assets/{seq_asset['id']}/agent-bundle", headers=eng_headers)
        assert bundle.status_code == 200
        assert "RESTIC_REPOSITORY" in bundle.json()["windows_powershell_script"]
        assert "RESTIC_REPOSITORY" in bundle.json()["unix_bash_script"]
        assert "seq-gen-004:" in bundle.json()["resticprofile_yaml"]

        # Verify resticprofile endpoints (/api/v1/policies/{id}/resticprofile and /api/v1/agents/profile.yaml)
        rp_resp = client.get(f"/api/v1/policies/{policy_id}/resticprofile", headers=eng_headers)
        assert rp_resp.status_code == 200
        rp_data = rp_resp.json()
        assert rp_data["valid"] is True
        assert rp_data["profile_name"] == "seq-gen-004"
        assert "seq-gen-004:" in rp_data["config_yaml"]
        assert "seq-gen-004" in rp_data["show_output"]

        agent_yaml_resp = client.get(
            "/api/v1/agents/profile.yaml",
            headers={"X-Agent-Token": seq_after["agent_token"]},
        )
        assert agent_yaml_resp.status_code == 200
        assert "seq-gen-004:" in agent_yaml_resp.text
        assert "*-*-* 03:15:00" in agent_yaml_resp.text

        # 9. Verify Equipment Backup Guides endpoint
        guides = client.get("/api/v1/sops/guides", headers=eng_headers)
        assert guides.status_code == 200
        assert len(guides.json()) >= 6

        # 10. Verify 21 CFR Part 11 Cryptographic Audit Chain Integrity
        audit_verify = client.get("/api/v1/audit/verify", headers=qa_headers)
        assert audit_verify.status_code == 200
        verify_json = audit_verify.json()
        assert verify_json["valid"] is True
        assert verify_json["total_records"] >= 5

    shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)
