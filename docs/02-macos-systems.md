# 02. macOS Lab Workstations Backup Guide

## Overview
macOS workstations are widely used in life sciences for **Flow Cytometry analysis (FlowJo)**, **High-Content Microscopy & ImageJ/Fiji**, **Single-Cell & Spatial Transcriptomics**, **Structural Biology (CryoSPARC / ChimeraX / PyMOL)**, and **Bioinformatics pipelines**.

### Key Requirements on macOS (macOS 13 Ventura / 14 Sonoma / 15 Sequoia+)
1. **Transparency, Consent, and Control (TCC) / Full Disk Access**: macOS restricts background daemons (`launchd`) from reading protected directories or external thunderbolt volumes unless granted **Full Disk Access**.
2. **Daemon Execution**: Use a system-level `LaunchDaemon` (`/Library/LaunchDaemons`) rather than a user `LaunchAgent` so backups execute even when lab staff log out.

---

## Step 1: Install Restic & `resticprofile` on macOS

### Option A: Homebrew
```bash
brew install restic creativeprojects/tap/resticprofile
```

### Option B: Direct Signed Binary (Standardized Path)
```bash
curl -L https://github.com/restic/restic/releases/download/v0.17.3/restic_0.17.3_darwin_arm64.bz2 | bunzip2 > /usr/local/bin/restic
chmod 0755 /usr/local/bin/restic
curl -L https://github.com/creativeprojects/resticprofile/releases/download/v0.33.1/resticprofile_0.33.1_darwin_arm64.tar.gz | tar -xz -C /usr/local/bin resticprofile
chmod 0755 /usr/local/bin/resticprofile
```

---

## Step 2: Grant Full Disk Access (TCC)
1. Open **System Settings → Privacy & Security → Full Disk Access**.
2. Click the **`+`** button, press `Cmd + Shift + G`, and add:
   - `/usr/local/bin/restic` (or `/opt/homebrew/bin/restic`)
   - `/bin/bash`
3. If your lab manages Macs via **Jamf Pro / Kandji / Mosyle**, deploy a **PPPC (Privacy Preferences Policy Control)** configuration profile granting `SystemPolicyAllFiles` to `/usr/local/bin/restic`.

---

## Step 3: Deploy the CFR-App macOS Agent Script

Save the following script to `/Library/Application Support/CFRApp/cfr-agent.sh` (or generate it with pre-filled tokens from the **CFR-App Web Portal**):

```bash
#!/usr/bin/env bash
set -euo pipefail

API_URL="${CFR_API_URL:-http://localhost:8080/api/v1}"
AGENT_TOKEN="${CFR_AGENT_TOKEN:-YOUR_ASSET_AGENT_TOKEN}"
FORCE_RUN="${1:-false}"

CONFIG_JSON=$(curl -fsSL -H "X-Agent-Token: ${AGENT_TOKEN}" "${API_URL}/agents/config")

POLICY_ENABLED=$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('policy_enabled', False))")
SHOULD_RUN=$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('should_run_now', False))")

if [[ "${POLICY_ENABLED}" != "True" ]]; then
  echo "Policy disabled centrally. Exiting."
  exit 0
fi

if [[ "${FORCE_RUN}" != "--force" && "${SHOULD_RUN}" != "True" ]]; then
  exit 0
fi

eval "$(echo "${CONFIG_JSON}" | python3 -c '
import sys, json, shlex
cfg = json.load(sys.stdin)
print(f"export RESTIC_REPOSITORY={shlex.quote(cfg[\"repository_uri\"])}")
print(f"export RESTIC_PASSWORD={shlex.quote(cfg[\"repository_password\"])}")
for k, v in (cfg.get("repository_env") or {}).items():
    print(f"export {k}={shlex.quote(str(v))}")
')"

ASSET_TAG=$(echo "${CONFIG_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['asset_tag'])")
PATHS_ARGS=$(echo "${CONFIG_JSON}" | python3 -c "import sys,json,shlex; print(' '.join(shlex.quote(p) for p in json.load(sys.stdin)['backup_paths']))")
EXCLUDE_ARGS=$(echo "${CONFIG_JSON}" | python3 -c "import sys,json,shlex; print(' '.join('--exclude=' + shlex.quote(x) for x in json.load(sys.stdin).get('exclude_patterns', [])))")

START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUTPUT_FILE=$(mktemp)

if eval "/usr/local/bin/restic backup --json --tag asset:${ASSET_TAG} ${EXCLUDE_ARGS} ${PATHS_ARGS}" > "${OUTPUT_FILE}" 2>&1; then
  STATUS="COMPLETED"
else
  STATUS="FAILED"
fi

END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
python3 - "${OUTPUT_FILE}" "${STATUS}" "${START_TIME}" "${END_TIME}" "${API_URL}" "${AGENT_TOKEN}" << 'EOF'
import sys, json, urllib.request

output_file, status, start_t, end_t, api_url, token = sys.argv[1:7]
raw = open(output_file).read()
summary = {}
for line in raw.splitlines():
    if '"message_type":"summary"' in line:
        try:
            summary = json.loads(line)
        except Exception:
            pass

payload = {
    "status": status,
    "started_at": start_t,
    "completed_at": end_t,
    "snapshot_id": summary.get("snapshot_id"),
    "files_new": summary.get("files_new", 0),
    "files_changed": summary.get("files_changed", 0),
    "files_unmodified": summary.get("files_unmodified", 0),
    "bytes_added": summary.get("data_added", 0),
    "total_bytes_processed": summary.get("total_bytes_processed", 0),
    "log_output": raw[-8000:],
    "error_message": None if status == "COMPLETED" else "Restic exited with non-zero code"
}

req = urllib.request.Request(
    f"{api_url}/agents/report",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "X-Agent-Token": token},
    method="POST"
)
urllib.request.urlopen(req, timeout=15)
EOF
rm -f "${OUTPUT_FILE}"
```

Make it executable and root-owned:
```bash
sudo chmod 0700 "/Library/Application Support/CFRApp/cfr-agent.sh"
sudo chown root:wheel "/Library/Application Support/CFRApp/cfr-agent.sh"
```

---

## Step 4: Configure the `launchd` Daemon

Create `/Library/LaunchDaemons/com.cfrapp.restic.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cfrapp.restic</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Library/Application Support/CFRApp/cfr-agent.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/cfrapp-restic.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/cfrapp-restic.err</string>
</dict>
</plist>
```

Load and start the daemon:
```bash
sudo chown root:wheel /Library/LaunchDaemons/com.cfrapp.restic.plist
sudo chmod 0644 /Library/LaunchDaemons/com.cfrapp.restic.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.cfrapp.restic.plist
```
