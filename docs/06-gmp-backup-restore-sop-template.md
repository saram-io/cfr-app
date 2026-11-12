# 06. Standard Operating Procedure (SOP): Computerized System Backup & Restore

- **SOP ID**: `SOP-IT-CSV-008`
- **Version**: `3.0`
- **Effective Date**: `2026-01-01`
- **Regulatory Scope**: FDA 21 CFR Part 11, FDA 21 CFR Part 211.68, EU GMP Annex 11 (Section 7.1 & 7.2), ICH Q7

---

## 1. Purpose
This Standard Operating Procedure (SOP) defines the requirements and step-by-step procedures for performing automated backups, monitoring backup health, executing emergency data restores, and conducting periodic Restore Verification Drills for computerized laboratory and manufacturing assets managed within the **CFR-App Asset & Backup Management System**.

## 2. Scope
Applies to all computerized systems classified as **GMP** and/or **Critical** in the Site Asset Register, including analytical instruments (HPLC, LC-MS, GC, Flow Cytometers, Sequencers), manufacturing controllers (Bioreactors, Environmental Monitors), and supporting laboratory servers.

## 3. Roles & Responsibilities
- **System Owner**: Defines Asset Criticality (`Critical`, `Major`, `Minor`), GMP applicability, target **RPO** (Recovery Point Objective), and target **RTO** (Recovery Time Objective).
- **Lab Engineer / CSV Administrator**: Configures Restic backup policies, manages storage repositories, resolves failed backup alerts within 24 hours, and executes scheduled Restore Verification Drills.
- **Quality Assurance (QA / Compliance)**: Reviews and electronically signs off on GMP policy modifications, SOP revisions, and periodic Restore Verification Drill records.

## 4. Backup Classification & Frequency Matrix

| Criticality & GMP Tier | Mandatory Backup? | Minimum Frequency (Target RPO) | Target RTO | Restore Drill Frequency |
| :--- | :--- | :--- | :--- | :--- |
| **GMP + Critical** | **MANDATORY** | Every 4–24 Hours (≤ 24h RPO) | ≤ 4 Hours | Every 90 Days (Quarterly) |
| **Non-GMP + Critical** | **MANDATORY** | Daily (≤ 24h RPO) | ≤ 8 Hours | Every 180 Days (Semi-Annually) |
| **GMP + Major** | **MANDATORY** | Daily (≤ 24h RPO) | ≤ 12 Hours | Annually |
| **Non-GMP + Major** | Recommended | Weekly | ≤ 24 Hours | Annually |
| **Minor (Stateless)** | Not Required | N/A | N/A | N/A |

## 5. Procedure: Executing a Restore Verification Drill (or Emergency Restore)
1. **Initiate Restore Record**:
   - Navigate to **CFR-App → Snapshots & Restore → New Restore / Verification Drill**.
   - Select the target **Asset**, the **Restic Snapshot ID**, and the applicable **SOP Reference**.
2. **Execute Restic Restore**:
   - Restore files into an isolated quarantine/verification directory (or target recovery path) using the CFR-App UI one-click restore or CLI command:
     ```bash
     restic -r <REPO_URI> restore <SNAPSHOT_ID> --target /var/restore/verification/<ASSET_TAG>
     ```
3. **Verify Completeness & Cryptographic Checksums**:
   - Confirm that the restored directory structure, file count, and total byte size match the snapshot metadata.
   - Verify the **SHA-256 Manifest** generated during restoration to confirm zero bit-rot or truncation.
   - Open at least one representative raw data file / sequence in the native instrument viewer or validate its header structure.
4. **Verify RTO Compliance**:
   - Confirm that the elapsed restoration time (`Actual RTO`) is within the asset's approved `Target RTO`.
5. **QA Electronic Signature Sign-Off (21 CFR Part 11)**:
   - A member of **Quality Assurance (`QA_Compliance`)** reviews the restore evidence, checklist items, and SHA-256 manifest, and applies their Electronic Signature (`Verified` / `Approved`) in `cfr-app`.
