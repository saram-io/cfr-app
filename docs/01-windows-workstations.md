# 01. Windows Lab Workstations & Instrument Controllers Backup Guide

## Overview
Windows workstations are the most common instrument controllers in GMP/GLP analytical and quality control laboratories (e.g., **Waters Empower / MassLynx**, **Agilent OpenLab CDS / ChemStation**, **Thermo Fisher Chromeleon / Xcalibur**, **SCIEX Analyst**, **Cytiva Unicorn**, **Bio-Rad CFX Maestro**).

### Key Challenges on Windows Lab PCs
1. **Locked Open Files**: Instrument acquisition software and embedded databases (SQLite, Microsoft Jet/Access, SQL Server Express, Firebird) hold exclusive file locks during sample runs.
2. **Operator Logouts / Shared Lab Accounts**: Backups must run reliably in the background even when no operator is logged in or when Windows is locked.
3. **GMP Change Control**: Changing backup frequency or retention should not require touching validated instrument software configurations.

---

## Step 1: Install Restic & `resticprofile` on Windows

### Option A: Using Winget / Scoop (Connected Lab Network)
Open an elevated **PowerShell (Run as Administrator)**:
```powershell
winget install --id restic.restic --exact --silent
winget install --id creativeprojects.resticprofile --exact --silent
```

### Option B: Air-Gapped / Restricted Lab VLAN Installation
1. Download the official signed Windows `restic_X.Y.Z_windows_amd64.zip` and `resticprofile_X.Y.Z_windows_amd64.zip` binaries from [github.com/restic/restic/releases](https://github.com/restic/restic/releases) and [github.com/creativeprojects/resticprofile/releases](https://github.com/creativeprojects/resticprofile/releases) on a staging machine and verify their `SHA256SUMS` signatures.
2. Copy `restic.exe` and `resticprofile.exe` to `C:\Program Files\Restic\`:
```powershell
New-Item -ItemType Directory -Force -Path "C:\Program Files\Restic"
Copy-Item .\restic.exe "C:\Program Files\Restic\restic.exe"
Copy-Item .\resticprofile.exe "C:\Program Files\Restic\resticprofile.exe"
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\Restic", "Machine")
```

---

## Step 2: Enable Volume Shadow Copy (VSS) for Open Instrument Files
Always pass `--use-fs-snapshot` to Restic on Windows. This instructs Restic to create a transient **NTFS Volume Shadow Copy (VSS)** before reading files, allowing clean, crash-consistent backups of open chromatogram sequences, method files, and local SQLite/SQL databases without interrupting an active analytical run.

> **Important**: `--use-fs-snapshot` requires the backup script to run under `NT AUTHORITY\SYSTEM` or an Administrator account.

Verify VSS is healthy on the workstation:
```powershell
vssadmin list writers
```

---

## Step 3: Deploy the Dynamic CFR-App Agent Script

Create `C:\ProgramData\CFRApp\cfr-agent.ps1` (or download the pre-configured script directly from the **CFR-App Web Portal → Equipment Guides → Script Generator**):

```powershell
# C:\ProgramData\CFRApp\cfr-agent.ps1
param(
    [string]$ApiUrl = "http://localhost:8080/api/v1",
    [string]$AgentToken = "YOUR_ASSET_AGENT_TOKEN",
    [switch]$ForceBackup
)

$ErrorActionPreference = "Stop"
$StateDir = "C:\ProgramData\CFRApp"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# 1. Poll Central CFR-App Server for current policy, schedule & credentials
$Headers = @{ "X-Agent-Token" = $AgentToken }
$Config = Invoke-RestMethod -Uri "$ApiUrl/agents/config" -Method Get -Headers $Headers

if (-not $Config.policy_enabled) {
    Write-Output "Backup policy is disabled centrally for $($Config.asset_tag). Exiting."
    exit 0
}

if (-not $ForceBackup -and -not $Config.should_run_now) {
    Write-Output "Next scheduled window not yet reached (Cron: $($Config.schedule_cron))."
    exit 0
}

# 2. Configure Restic environment variables dynamically from central vault
$env:RESTIC_REPOSITORY = $Config.repository_uri
$env:RESTIC_PASSWORD   = $Config.repository_password
foreach ($kv in $Config.repository_env.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($kv.Name, $kv.Value, "Process")
}

# 3. Execute Restic Backup with Volume Shadow Copy (VSS)
$StartTime = (Get-Date).ToUniversalTime().ToString("o")
$ArgsList = @("backup", "--json", "--tag", "asset:$($Config.asset_tag)", "--tag", "gmp:$($Config.is_gmp)")
if ($Config.vss_enabled) { $ArgsList += "--use-fs-snapshot" }
foreach ($ex in $Config.exclude_patterns) { $ArgsList += "--exclude=$ex" }
foreach ($p in $Config.backup_paths) { $ArgsList += $p }

try {
    $Output = & "C:\Program Files\Restic\restic.exe" @ArgsList 2>&1 | Out-String
    $SummaryLine = ($Output -split "`n" | Where-Object { $_ -match '"message_type":"summary"' } | Select-Object -Last 1)
    $Summary = if ($SummaryLine) { $SummaryLine | ConvertFrom-Json } else { $null }

    $Payload = @{
        status                = "COMPLETED"
        started_at            = $StartTime
        completed_at          = (Get-Date).ToUniversalTime().ToString("o")
        snapshot_id           = if ($Summary) { $Summary.snapshot_id } else { "unknown" }
        files_new             = if ($Summary) { $Summary.files_new } else { 0 }
        files_changed         = if ($Summary) { $Summary.files_changed } else { 0 }
        files_unmodified      = if ($Summary) { $Summary.files_unmodified } else { 0 }
        bytes_added           = if ($Summary) { $Summary.data_added } else { 0 }
        total_bytes_processed = if ($Summary) { $Summary.total_bytes_processed } else { 0 }
        log_output            = $Output
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod -Uri "$ApiUrl/agents/report" -Method Post -Headers $Headers -ContentType "application/json" -Body $Payload
} catch {
    $ErrPayload = @{
        status        = "FAILED"
        started_at    = $StartTime
        completed_at  = (Get-Date).ToUniversalTime().ToString("o")
        error_message = $_.Exception.Message
        log_output    = $_.ScriptStackTrace
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri "$ApiUrl/agents/report" -Method Post -Headers $Headers -ContentType "application/json" -Body $ErrPayload
    throw
}
```

---

## Step 4: Register with Windows Task Scheduler (`NT AUTHORITY\SYSTEM`)

Because the agent script polls the central CFR-App server for its active schedule, register a lightweight 5-minute heartbeat task in Windows Task Scheduler. Whenever you change the backup frequency in the CFR-App UI (e.g., from Daily to Every 4 Hours), the Windows PC automatically follows the new schedule without touching Task Scheduler again:

```powershell
$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"C:\ProgramData\CFRApp\cfr-agent.ps1`""
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "CFRApp-GMP-Restic-Agent" `
    -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force
```

---

## Recommended Instrument Paths & Exclusions on Windows

| Instrument Suite | Typical Raw Data & Method Paths | Recommended Exclusions |
| :--- | :--- | :--- |
| **Waters Empower / MassLynx** | `C:\Empower\Projects`, `D:\MassLynx\*.PRO` | `*.tmp`, `*.lck`, `*\Temp\*` |
| **Agilent OpenLab / ChemStation** | `C:\Chem32\1\Data`, `C:\Chem32\1\Methods` | `*.bak`, `*\Cache\*` |
| **Thermo Chromeleon / Xcalibur** | `C:\Chromeleon\Data`, `D:\Xcalibur\data` | `*.tmp`, `pagefile.sys` |
| **SCIEX Analyst** | `D:\Analyst Data\Projects` | `*.wiff.lock` |
