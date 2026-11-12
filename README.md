# CFR-App: Life Science Asset & GxP Restic Backup Management System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Compliance: 21 CFR Part 11 / EU Annex 11](https://img.shields.io/badge/GxP-21%20CFR%20Part%2011%20%7C%20Annex%2011-indigo.svg)](#)
[![Backup Engine: Restic](https://img.shields.io/badge/Backup-Restic%20%2B%20REST%20Server-emerald.svg)](https://restic.net/)

An open-source (**MIT License**), turnkey Dockerized asset management and backup/restore lifecycle platform engineered for **Life Science companies (Biotech, Pharma, MedTech, Contract Research/Manufacturing Organizations, and Clinical Diagnostics)**.

---

## Why `cfr-app`?

In regulated GxP laboratories and manufacturing suites, analytical instruments (**HPLC/UPLC, LC-MS/MS, Flow Cytometers, NGS Sequencers, Bioreactors, qPCR**) generate raw data subject to **FDA 21 CFR Part 11**, **21 CFR Part 211.68**, and **EU GMP Annex 11 (§7.1 Data Storage & §17 Archiving)**.

`cfr-app` bridges the gap between **Quality Assurance (QA/CSV)** and **Lab IT/OT Engineering** by combining:
1. **Asset Criticality & GMP Classification Register**: Track every piece of equipment, its `GMP` vs. `Non-GMP` status, and its Criticality (`CRITICAL`, `MAJOR`, `MINOR`).
2. **Automated GxP Compliance Watchdog**: Any `CRITICAL` or `GMP` asset is automatically monitored and flagged `NON_COMPLIANT` or `AT_RISK` unless it has:
   - An active **Restic Backup Policy**
   - A linked, QA-approved **Backup & Restore SOP**
   - A successful encrypted snapshot within its **RPO (Recovery Point Objective)**
   - A completed, SHA-256 checksum-verified **Restore Verification Drill** within its required window (e.g., 90 days) signed off by QA.
3. **Centralized Restic, `resticprofile` & Restic REST Server Orchestration**:
   - Manage backup frequency (Hourly, Every 4h, Daily, Weekly, or custom Cron), paths, exclusions, Windows Volume Shadow Copy (`--use-fs-snapshot`), and retention (`--keep-daily`, `--keep-weekly`, `--keep-monthly`, `--keep-yearly`) directly from the web UI.
   - Automatically generates and validates declarative **`resticprofile` (`profiles.yaml`)** configurations per asset (`/api/v1/policies/{id}/resticprofile` and `/api/v1/agents/profile.yaml`), complete with `retention`, `check`, OS scheduler definitions, and `send-after` / `send-after-fail` HTTP reporting hooks.
   - Endpoints running `resticprofile` or the lightweight self-updating wrapper script automatically pull schedule edits from `cfr-app`—no need to log into individual lab workstations to change cron/Task Scheduler jobs.
4. **Multi-Backend Storage Support (3-2-1-1-0 Ready)**:
   - Bundled **Restic REST Server (`restic/rest-server`)** running in `--append-only` immutable mode to protect GMP backups against ransomware or accidental deletion.
   - Bundled **MinIO S3-Compatible Object Storage** for local on-prem S3 testing.
   - Native support for **AWS S3 (with S3 Object Lock WORM)**, **Ceph / NetApp StorageGRID / Wasabi**, **Azure Blob Storage**, **Google Cloud Storage**, **Backblaze B2**, **SFTP**, and **Local/NAS Vaults**.
5. **Agentless Backup Gateway for Closed / Legacy Lab Equipment**:
   - Built-in support and complete documentation for equipment where Restic cannot be installed (e.g., Bioreactor PLCs, Windows XP/2000/7 legacy controllers, plate readers, cleanroom analyzers) using **Read-Only SMB/CIFS or NFS Pull**, **SFTP/FTP Landing Zones**, or **USB-Gadget / Validated Sneaker-Net workflows**.
6. **21 CFR Part 11 Electronic Signatures & SHA-256 Hash-Chained Audit Trail**:
   - Role-Based Access Control (`Admin`, `QA_Compliance`, `Lab_Engineer`, `Auditor`).
   - Re-authentication Electronic Signature modal (`Approved`, `Verified`, `Reviewed`, `Authored` + mandatory reason for change) on GMP state changes and Restore Drill sign-offs.
   - Cryptographically linked SHA-256 audit log with one-click chain integrity verification and JSON inspection export.

---

## Quickstart with Docker Compose

Bring up the entire stack (`PostgreSQL 16`, `Restic REST Server (--append-only)`, `MinIO S3`, `FastAPI + Restic Gateway Backend`, and `React + Tailwind Web Portal`) with a single command:

```bash
cp .env.example .env
docker compose up --build -d
```

### Service Endpoints

| Service | URL | Default Credentials / Notes |
| :--- | :--- | :--- |
| **CFR-App Web Portal** | `http://localhost:8080` | `qa_director`, `admin`, `lab_eng`, or `fda_auditor` / Password: `gmp-password-123` |
| **FastAPI Backend & OpenAPI Docs** | `http://localhost:8001/docs` | Interactive Swagger UI & REST API |
| **Restic REST Server (`--append-only`)** | `http://localhost:8000` | Immutable Restic target (`rest:http://restic-server:8000/<repo>`) |
| **MinIO S3 Console** | `http://localhost:9001` | `minioadmin` / `minioadmin_secret_change_me` (S3 API on `:9000`) |

---

## Complete Equipment Backup Guidelines (`/docs`)

All guidelines are accessible both in the repository's [`/docs`](./docs) folder and interactively inside the **CFR-App Web Portal → Equipment Guides & SOPs** tab:

1. [**01. Windows Lab Workstations & Instrument Controllers**](./docs/01-windows-workstations.md) — Installing Restic, enabling Volume Shadow Copy (`--use-fs-snapshot`) for open Empower/ChemStation/Chromeleon/MassLynx files, and registering with Windows Task Scheduler (`NT AUTHORITY\SYSTEM`).
2. [**02. macOS Lab Workstations**](./docs/02-macos-systems.md) — Granting Full Disk Access (TCC) to `/usr/local/bin/restic` and running a root `LaunchDaemon` (`/Library/LaunchDaemons/com.cfrapp.restic.plist`).
3. [**03. Linux & Unix Lab Systems**](./docs/03-linux-unix-systems.md) — Least-privilege backups using POSIX capabilities (`CAP_DAC_READ_SEARCH`), pre-backup database dump hooks, and `systemd` service/timer units.
4. [**04. Equipment Where Restic Cannot Be Installed (Agentless & Legacy Systems)**](./docs/04-agentless-and-legacy-equipment.md) — Detailed architectures for **Read-Only SMB/CIFS & NFS Pull** (Windows XP/7), **SFTP/FTP Push to Landing Zones** (PLCs, Bioreactors, Plate Readers), and **USB-Gadget / Sneaker-Net** (Air-gapped Cleanroom Instruments).
5. [**05. Multi-Backend Storage Architecture & 3-2-1 GxP Strategy**](./docs/05-storage-backends-and-3-2-1-strategy.md) — Configuring Restic REST Server, AWS S3 Object Lock (WORM), MinIO, Azure Blob, GCS, Backblaze B2, and NAS.
6. [**06. Standard Operating Procedure (SOP) Template: Backup & Restore**](./docs/06-gmp-backup-restore-sop-template.md) — Ready-to-adopt QMS SOP template (`SOP-IT-CSV-008`) defining RPO/RTO tiers, restore verification checklists, and QA sign-off criteria.

---

## Local Development & Running Automated Tests

### Backend (`pytest` + Real Restic CLI Integration)
```bash
cd backend
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
PYTHONPATH=. .venv/bin/pytest -v tests/test_api.py
```

### Frontend (`Vite + React + TypeScript`)
```bash
cd frontend
npm install
npm run build
```

---

## License
Distributed under the [MIT License](./LICENSE). Any life science organization may freely deploy, modify, validate, and operate this software on-premises or in the cloud.
