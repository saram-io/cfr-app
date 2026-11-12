# 04. Equipment Where Restic Cannot Be Installed (Agentless & Legacy Systems)

## Overview
In regulated pharmaceutical, biotech, and clinical manufacturing facilities, many critical assets **cannot have third-party agents or Restic binaries installed directly on them** due to:
1. **Closed / Embedded Operating Systems**: Bioreactor PLCs (Siemens SIMATIC, Allen-Bradley), FPLC controllers, automated liquid handlers (Hamilton, Tecan), plate readers, balances, and particle counters.
2. **Vendor Validation Lock**: Installing software on a vendor-qualified controller voids the vendor's IQ/OQ validation package.
3. **Legacy End-of-Life OS**: Instruments anchored to **Windows XP, Windows 2000, Windows 7, or Solaris/IRIX** that cannot run modern 64-bit Go binaries and are isolated on an air-gapped or firewalled Instrument VLAN.

`cfr-app` solves this natively with the **Central Agentless Backup Gateway** built into the backend container.

---

## Architecture Comparison: Choosing the Right Agentless Pattern

| Pattern | Best For | Direction | Network Requirement |
| :--- | :--- | :--- | :--- |
| **Pattern A: Read-Only SMB/CIFS or NFS Pull** | Windows XP/7/10 controllers, NAS-backed microscopes, sequencers | Gateway pulls from Instrument | Port 445 (SMB) or 2049 (NFS) from CFR Gateway to Instrument VLAN |
| **Pattern B: SFTP / FTP / Rsync Landing Zone** | Embedded PLCs, Bioreactors, Plate Readers, Balances with "Export to FTP/SFTP" | Instrument pushes to Gateway | Port 22 (SFTP) or 21 (FTP) from Instrument to CFR Gateway |
| **Pattern C: USB-Gadget / Air-Gapped Sneaker-Net** | Completely disconnected cleanroom equipment with only USB/Serial ports | Validated USB / Edge Bridge | Zero network on instrument |

---

## Pattern A: Read-Only SMB/CIFS or NFS Pull (Most Common for Legacy Windows XP/7)

### How It Works
Instead of installing Restic on the legacy PC, you share the instrument's raw data folder as a **Read-Only SMB Share** restricted to a dedicated service account (`cfr_backup_svc`), and the CFR-App Gateway mounts it read-only during scheduled backup windows.

### Step-by-Step Setup
1. **On the Instrument PC (Windows XP / 7 / 10)**:
   - Create a local non-admin user `cfr_backup_svc` with a strong password.
   - Right-click the raw data directory (e.g., `D:\InstrumentData`) → **Properties → Sharing → Advanced Sharing**.
   - Grant `cfr_backup_svc` **Read** permission ONLY (never grant Write/Modify permissions, protecting the instrument from external tampering).
2. **In the CFR-App Web Portal**:
   - Register the Asset with `OS / Connection Type = AGENTLESS_SMB`.
   - Create a Backup Policy with `Execution Mode = CENTRAL_GATEWAY`.
   - Set the Gateway Source Path or Mountpoint (e.g., `/mnt/instruments/bioreactor-01` or a staging sync path).
3. **Host/Container Read-Only CIFS Mount** (`/etc/fstab` on Docker Host or Gateway):
   ```bash
   # Mount legacy instrument SMB share strictly read-only (ro)
   //10.20.30.15/InstrumentData  /mnt/instruments/hplc-legacy-xp  cifs  ro,vers=2.1,username=cfr_backup_svc,password=REDACTED,uid=1000,gid=1000,nofail  0  0
   ```
   > **Note for Windows XP / 2000**: If the legacy controller only speaks SMBv1, isolate it on a dedicated point-to-point VLAN to the Backup Gateway and specify `ro,vers=1.0,sec=ntlmssp`.

---

## Pattern B: SFTP / FTP Push to Hardened Landing Zone

Many embedded instruments (e.g., **Beckman Coulter Vi-CELL**, **Sartorius Ambr / Biostat**, **Mettler Toledo LabX**, **Roche Cedex**, **Environmental Particle Counters**) include a built-in *"Automated Export to SFTP/FTP Server"* or *"Network Folder Watch"* feature after each batch run.

### Step-by-Step Setup
1. Configure a dedicated per-asset Landing Zone directory inside the CFR-App Gateway volume:
   ```text
   /app/data/landing_zones/<ASSET_TAG>/
   ```
2. Point the instrument's built-in SFTP/FTP export settings to the CFR-App server's SFTP Landing Zone directory using chrooted credentials.
3. In the **CFR-App Web Portal**, create a Backup Policy for the asset with:
   - `Execution Mode`: `CENTRAL_GATEWAY`
   - `Backup Paths`: `["/app/data/landing_zones/<ASSET_TAG>"]`
   - `Schedule`: Hourly or Every 4 Hours (or trigger immediately via webhook on file arrival).
4. The CFR-App Gateway snapshots the Landing Zone into the encrypted Restic repository (with deduplication, so unchanged historical run files consume zero extra storage).

---

## Pattern C: Air-Gapped / Cleanroom Equipment (USB Gadget Bridge or Validated Sneaker-Net)

For Grade A/B cleanroom equipment or standalone analyzers with **zero network interfaces**:

### Option 1: Raspberry Pi / Industrial Edge USB-to-Restic Bridge
1. Connect an industrial Linux SBC (e.g., Raspberry Pi CM4 / Kunbus Revolution Pi) to the instrument's USB port configured as a **Linux USB Mass Storage Gadget (`g_mass_storage`)**.
2. To the instrument, the device appears as a standard FAT32/exFAT USB flash drive where operators export run PDFs/CSVs.
3. On the Linux SBC, a read-only loop mount inspects the backing image file every 15 minutes and runs `restic backup` over Wi-Fi / Cleanroom Ethernet to the CFR-App Restic REST Server.

### Option 2: Validated Manual USB Sneaker-Net Workflow (SOP Controlled)
When physical USB transfer is the only permitted mechanism:
1. Operator inserts a serialized, QA-controlled encrypted USB drive into the instrument and exports the run batch.
2. Operator inserts the USB drive into a networked **GMP Transfer Kiosk** and runs the CFR-App Ingestion helper:
   ```bash
   # Generates SHA-256 manifest, backs up to Restic, and logs to CFR-App
   restic -r rest:http://cfr-server:8000/cleanroom-assets backup /media/usb-gmp-01 \
     --tag "asset:CLEANROOM-PARTICLE-01" --tag "operator:jdoe"
   ```
3. Verify the snapshot appears in **CFR-App → Snapshots & Restore** before clearing the USB transfer media.
