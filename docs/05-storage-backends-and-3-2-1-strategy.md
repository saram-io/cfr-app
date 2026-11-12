# 05. Multi-Backend Storage Architecture & 3-2-1 GxP Strategy

## Overview
Restic natively supports content-addressable, AES-256 encrypted, deduplicated repositories across local, network, and cloud object storage backends. `cfr-app` lets you manage and monitor all of these storage backends from a single pane of glass.

---

## Supported Storage Backends in `cfr-app`

| Backend Type | Repository URI Format | Required Credentials / Env Vars | Immutability (WORM / Ransomware Protection) |
| :--- | :--- | :--- | :--- |
| **Restic REST Server** *(Bundled in Docker)* | `rest:http://restic-server:8000/<repo_name>` | Optional HTTP Basic Auth (`RESTIC_REST_USERNAME`, `RESTIC_REST_PASSWORD`) | `--append-only` flag prevents deletion or modification of existing snapshots |
| **AWS S3** | `s3:s3.amazonaws.com/<bucket>/<prefix>` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | **S3 Object Lock** (Compliance or Governance Mode) |
| **MinIO (On-Prem S3)** *(Bundled in Docker)* | `s3:http://minio:9000/<bucket>/<prefix>` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | MinIO Bucket Object Locking / Versioning |
| **Ceph / Wasabi / NetApp StorageGRID** | `s3:https://<endpoint>/<bucket>/<prefix>` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 Object Lock |
| **Azure Blob Storage** | `azure:<container>:/<prefix>` | `AZURE_ACCOUNT_NAME`, `AZURE_ACCOUNT_KEY` | Azure Immutable Blob Storage Policy |
| **Google Cloud Storage** | `gs:<bucket>:/<prefix>` | `GOOGLE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | GCS Bucket Retention Policy Lock |
| **Backblaze B2** | `b2:<bucket>:<prefix>` | `B2_ACCOUNT_ID`, `B2_ACCOUNT_KEY` | B2 Object Lock |
| **SFTP / Enterprise NAS** | `sftp:user@host:/srv/restic/<repo>` or `/app/data/repos/<repo>` | SSH Key or Mounted Volume | NAS Snapshot Lock (NetApp SnapLock / ZFS read-only snapshots) |

---

## Designing a 3-2-1-1-0 Backup Architecture for GMP Compliance

For **Critical GMP Assets**, regulatory inspectors (FDA, EMA, MHRA, PMDA) expect resilience against both hardware failure and cyber/ransomware incidents:

1. **3 Copies of Data**:
   - Copy 1: Primary instrument acquisition disk / RAID array.
   - Copy 2: Local On-Premises **Restic REST Server** (`--append-only`) or **MinIO Appliance** on the site network (fast local restores for low RTO).
   - Copy 3: Off-site Cloud Object Storage (**AWS S3**, **Azure Blob**, or **Backblaze B2**).
2. **2 Different Storage Media**: Local NVMe/SAN + Cloud Object Storage.
3. **1 Off-Site Copy**: Geographically separated region.
4. **1 Immutable Copy**: `--append-only` Restic REST Server + S3 Object Lock.
5. **0 Unverified Backups**: Scheduled automated `restic check` integrity scans and quarterly **SOP Restore Verification Drills** logged in `cfr-app` with QA Electronic Signatures.
