# 03. Linux & Unix Lab Systems Backup Guide

## Overview
Linux and Unix systems power high-throughput life science instruments and compute nodes, including:
- **NGS Sequencers** (Illumina NovaSeq / NextSeq local Linux compute, Oxford Nanopore PromethION/GridION Ubuntu towers)
- **Cryo-EM & Structural Biology** (FEI/Thermo Titan Krios Linux storage servers, Gatan K3 detector nodes)
- **NMR Spectrometers** (Bruker TopSpin RHEL/AlmaLinux workstations)
- **On-Premises LIMS, ELN, and Relational Databases** (PostgreSQL, MariaDB, Oracle)

---

## Step 1: Least-Privilege Restic & `resticprofile` Installation (`CAP_DAC_READ_SEARCH`)

For GMP security hardening, avoid running Restic as full `root` when possible. Instead, create a dedicated `restic-backup` service user and grant the `restic` binary the POSIX `CAP_DAC_READ_SEARCH` capability so it can read all instrument data directories without write/root privileges:

```bash
# Install restic and resticprofile (Ubuntu/Debian or RHEL/Rocky/AlmaLinux)
sudo apt-get update && sudo apt-get install -y restic || sudo dnf install -y restic
curl -fsSL https://github.com/creativeprojects/resticprofile/releases/download/v0.33.1/resticprofile_0.33.1_linux_amd64.tar.gz | sudo tar -xz -C /usr/local/bin resticprofile
sudo chmod 0755 /usr/local/bin/resticprofile

# Create dedicated backup service account
sudo useradd --system --home-dir /var/lib/cfr-agent --create-home --shell /usr/sbin/nologin restic-backup

# Restrict binary execution to restic-backup group and grant read-only filesystem capability
sudo chown root:restic-backup /usr/bin/restic
sudo chmod 0750 /usr/bin/restic
sudo setcap cap_dac_read_search=+ep /usr/bin/restic
```

---

## Step 2: Pre-Backup Database Dump Hook (LIMS / ELN / Instrument DBs)

If the Linux server runs PostgreSQL or MySQL/MariaDB alongside raw instrument files, create a pre-backup hook in `/etc/cfr-agent/pre-backup.sh` so database dumps are captured atomically prior to the Restic snapshot:

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p /var/backups/gmp-db
pg_dumpall -U postgres --clean | gzip > /var/backups/gmp-db/postgres_full.sql.gz
chmod 0600 /var/backups/gmp-db/postgres_full.sql.gz
```

---

## Step 3: Deploy the Systemd Service & Timer

1. Install the agent script at `/usr/local/bin/cfr-agent.sh` (generated via **CFR-App Web Portal → Equipment Guides → Script Generator**).
2. Create `/etc/systemd/system/cfr-restic-agent.service`:

```ini
[Unit]
Description=CFR-App GxP Restic Backup Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=restic-backup
Group=restic-backup
EnvironmentFile=/etc/cfr-agent/agent.env
ExecStart=/usr/local/bin/cfr-agent.sh
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6
```

3. Create `/etc/systemd/system/cfr-restic-agent.timer`:

```ini
[Unit]
Description=Poll CFR-App Backup Schedule Every 5 Minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

4. Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cfr-restic-agent.timer
sudo systemctl list-timers cfr-restic-agent.timer
```
