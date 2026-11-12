import React, { useEffect, useId, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Code2,
  Edit3,
  Play,
  Plus,
} from "lucide-react"
import { apiRequest } from "../api/client"
import { ESignatureFields } from "../components/ESignatureFields"
import { ModalDialog } from "../components/ModalDialog"
import { CriticalityBadge, GmpBadge } from "../components/StatusBadges"
import {
  Asset,
  BackupPolicy,
  ElectronicSignatureInput,
  StorageRepo,
  User,
} from "../types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface ResticProfileValidation {
  profile_name: string
  config_yaml: string
  gateway_profile_path: string
  resticprofile_binary?: string | null
  valid: boolean
  show_output: string
}

export const PoliciesView: React.FC<{ currentUser: User }> = ({
  currentUser,
}) => {
  const captionId = useId()
  const formId = useId()

  const [policies, setPolicies] = useState<BackupPolicy[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [repos, setRepos] = useState<StorageRepo[]>([])
  const [runningPolicyId, setRunningPolicyId] = useState<number | null>(null)
  const [lastRunBanner, setLastRunBanner] = useState<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [profilePreview, setProfilePreview] =
    useState<ResticProfileValidation | null>(null)
  const [profilePreviewTab, setProfilePreviewTab] = useState<"yaml" | "show">(
    "yaml"
  )

  // Form state
  const [selectedAssetId, setSelectedAssetId] = useState<number>(0)
  const [selectedRepoId, setSelectedRepoId] = useState<number>(0)
  const [policyName, setPolicyName] = useState("")
  const [isEnabled, setIsEnabled] = useState(true)
  const [executionMode, setExecutionMode] = useState<
    "ENDPOINT_AGENT" | "CENTRAL_GATEWAY"
  >("ENDPOINT_AGENT")
  const [schedulePreset, setSchedulePreset] = useState<
    "HOURLY" | "EVERY_4_HOURS" | "DAILY" | "WEEKLY" | "CUSTOM"
  >("DAILY")
  const [scheduleCron, setScheduleCron] = useState("0 2 * * *")
  const [backupPathsText, setBackupPathsText] = useState("")
  const [excludePatternsText, setExcludePatternsText] =
    useState("*.tmp, *.lck")
  const [rpoHours, setRpoHours] = useState(24)
  const [rtoHours, setRtoHours] = useState(4)
  const [keepLast, setKeepLast] = useState(7)
  const [keepDaily, setKeepDaily] = useState(14)
  const [keepWeekly, setKeepWeekly] = useState(8)
  const [keepMonthly, setKeepMonthly] = useState(12)
  const [keepYearly, setKeepYearly] = useState(7)
  const [vssEnabled, setVssEnabled] = useState(true)
  const [esig, setEsig] = useState<ElectronicSignatureInput>({
    username: currentUser.username,
    password: "gmp-password-123",
    meaning: "Approved",
    reason: "",
  })

  const loadAll = async () => {
    const [pols, asts, rps] = await Promise.all([
      apiRequest<BackupPolicy[]>("/policies"),
      apiRequest<Asset[]>("/assets"),
      apiRequest<StorageRepo[]>("/storage"),
    ])
    setPolicies(pols)
    setAssets(asts)
    setRepos(rps)
  }

  useEffect(() => {
    loadAll()
  }, [])

  const openModalForAsset = (asset: Asset, existingPolicy?: BackupPolicy) => {
    setErrorMsg(null)
    setSelectedAssetId(asset.id)
    setSelectedRepoId(existingPolicy?.repository_id ?? repos[0]?.id ?? 1)
    setPolicyName(
      existingPolicy?.name ?? `${asset.asset_tag} Standard Restic Backup Policy`
    )
    setIsEnabled(existingPolicy?.is_enabled ?? true)
    setExecutionMode(
      existingPolicy?.execution_mode ??
        (asset.os_type.startsWith("AGENTLESS")
          ? "CENTRAL_GATEWAY"
          : "ENDPOINT_AGENT")
    )
    setSchedulePreset(existingPolicy?.schedule_preset ?? "DAILY")
    setScheduleCron(existingPolicy?.schedule_cron ?? "0 2 * * *")
    setBackupPathsText(
      existingPolicy
        ? existingPolicy.backup_paths.join(", ")
        : `/app/data/sample_instruments/${asset.asset_tag}`
    )
    setExcludePatternsText(
      existingPolicy
        ? existingPolicy.exclude_patterns.join(", ")
        : "*.tmp, *.lck, *~"
    )
    setRpoHours(existingPolicy?.rpo_hours ?? 24)
    setRtoHours(existingPolicy?.rto_hours ?? 4)
    setKeepLast(existingPolicy?.retention_keep_last ?? 7)
    setKeepDaily(existingPolicy?.retention_keep_daily ?? 14)
    setKeepWeekly(existingPolicy?.retention_keep_weekly ?? 8)
    setKeepMonthly(existingPolicy?.retention_keep_monthly ?? 12)
    setKeepYearly(existingPolicy?.retention_keep_yearly ?? 7)
    setVssEnabled(
      existingPolicy?.vss_enabled ?? asset.os_type === "WINDOWS"
    )
    setEsig({
      username: currentUser.username,
      password: "gmp-password-123",
      meaning: "Approved",
      reason: existingPolicy
        ? "Updated Restic backup schedule / retention policy"
        : "Initial Restic backup policy assignment",
    })
    setIsModalOpen(true)
  }

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)

    const paths = backupPathsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
    const excludes = excludePatternsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)

    try {
      await apiRequest("/policies", {
        method: "POST",
        body: JSON.stringify({
          asset_id: selectedAssetId,
          repository_id: selectedRepoId,
          name: policyName,
          is_enabled: isEnabled,
          execution_mode: executionMode,
          schedule_preset: schedulePreset,
          schedule_cron: scheduleCron,
          backup_paths: paths,
          exclude_patterns: excludes,
          rpo_hours: Number(rpoHours),
          rto_hours: Number(rtoHours),
          retention_keep_last: Number(keepLast),
          retention_keep_daily: Number(keepDaily),
          retention_keep_weekly: Number(keepWeekly),
          retention_keep_monthly: Number(keepMonthly),
          retention_keep_yearly: Number(keepYearly),
          vss_enabled: vssEnabled,
          esignature: esig,
        }),
      })
      setIsModalOpen(false)
      await loadAll()
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save backup policy")
    }
  }

  const handleRunBackupNow = async (pol: BackupPolicy) => {
    setRunningPolicyId(pol.id)
    setLastRunBanner(null)
    try {
      const res = await apiRequest<{
        status: string
        snapshot_id: string
        duration_seconds: number
        total_bytes_processed: number
        error_message?: string
      }>(`/policies/${pol.id}/run-now`, { method: "POST" })
      if (res.status === "COMPLETED") {
        setLastRunBanner(
          `Restic backup COMPLETED for ${pol.asset_tag}! Created encrypted snapshot ${res.snapshot_id.slice(
            0,
            8
          )} (${res.total_bytes_processed} bytes processed in ${res.duration_seconds}s).`
        )
      } else {
        setLastRunBanner(
          `Backup failed for ${pol.asset_tag}: ${res.error_message}`
        )
      }
      await loadAll()
    } catch (err: any) {
      setLastRunBanner(`Error running backup: ${err.message}`)
    } finally {
      setRunningPolicyId(null)
    }
  }

  const openResticProfileModal = async (pol: BackupPolicy) => {
    const res = await apiRequest<ResticProfileValidation>(
      `/policies/${pol.id}/resticprofile`
    )
    setProfilePreview(res)
    setProfilePreviewTab("yaml")
  }

  const unconfiguredAssets = assets.filter(
    (a) =>
      !policies.some((p) => p.asset_id === a.id) &&
      (a.criticality === "CRITICAL" || a.is_gmp)
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            Restic Backup Policies, Schedules &amp; Retention Control
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage backup frequency, paths, VSS snapshots, and retention rules
            centrally. Endpoint agents automatically adopt updated schedules on
            their next poll.
          </p>
        </div>
        {currentUser.role !== "Auditor" && assets.length > 0 && (
          <Button
            onClick={() =>
              openModalForAsset(unconfiguredAssets[0] || assets[0])
            }
          >
            <Plus data-icon="inline-start" aria-hidden="true" />
            Configure Asset Backup Policy
          </Button>
        )}
      </div>

      {lastRunBanner && (
        <Alert role="status">
          <CheckCircle2 aria-hidden="true" />
          <AlertTitle>Restic Backup Status</AlertTitle>
          <AlertDescription>{lastRunBanner}</AlertDescription>
        </Alert>
      )}

      {unconfiguredAssets.length > 0 && (
        <Alert
          variant="destructive"
          className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle
              className="mt-0.5 size-4 shrink-0"
              aria-hidden="true"
            />
            <div className="flex flex-col gap-0.5">
              <AlertTitle>Compliance Action Required</AlertTitle>
              <AlertDescription>
                {unconfiguredAssets.length} Critical/GMP asset(s) currently lack
                an active Restic backup policy:{" "}
                {unconfiguredAssets.map((u) => u.asset_tag).join(", ")}.
              </AlertDescription>
            </div>
          </div>
          {currentUser.role !== "Auditor" && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => openModalForAsset(unconfiguredAssets[0])}
              className="shrink-0"
            >
              Configure {unconfiguredAssets[0].asset_tag} Now
            </Button>
          )}
        </Alert>
      )}

      <Card className="p-0">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby={captionId}
          className="table-wrapper"
        >
          <Table className="text-xs">
            <TableCaption id={captionId} className="sr-only">
              Restic Backup Policies and Schedules
            </TableCaption>
            <TableHeader className="bg-muted/60 tracking-wider uppercase">
              <TableRow>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Asset &amp; Policy
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Execution Mode &amp; Vault
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Schedule &amp; RPO / RTO
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Retention Policy
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Paths &amp; Last Run
                </TableHead>
                <TableHead
                  scope="col"
                  className="px-4 py-3 text-right font-bold"
                >
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {policies.map((p) => {
                const assetObj = assets.find((a) => a.id === p.asset_id)
                return (
                  <TableRow key={p.id}>
                    <TableHead
                      scope="row"
                      className="border-r px-4 py-3.5 font-normal whitespace-normal"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-primary">
                          {p.asset_tag}
                        </span>
                        <GmpBadge isGmp={p.is_gmp} />
                        <CriticalityBadge criticality={p.criticality} />
                      </div>
                      <div className="mt-1 text-sm font-semibold text-foreground">
                        {p.asset_name}
                      </div>
                      <div className="text-muted-foreground">
                        Policy Rev: v{p.config_version}
                      </div>
                    </TableHead>
                    <TableCell className="px-4 py-3.5">
                      <Badge variant="sky">{p.execution_mode}</Badge>
                      <div className="mt-1 font-medium text-foreground">
                        {p.repository_name}
                      </div>
                      <div className="text-muted-foreground">
                        Backend: {p.backend_type}{" "}
                        {p.vss_enabled ? "• VSS Enabled" : ""}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5">
                      <div className="inline-flex items-center gap-1 font-semibold text-foreground">
                        <Clock
                          className="size-3.5 text-primary"
                          aria-hidden="true"
                        />
                        {p.schedule_preset} (
                        <code className="font-mono">{p.schedule_cron}</code>)
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        Target RPO:{" "}
                        <strong className="text-foreground">
                          &le;{p.rpo_hours}h
                        </strong>{" "}
                        &bull; Target RTO:{" "}
                        <strong className="text-foreground">
                          &le;{p.rto_hours}h
                        </strong>
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5 font-mono text-muted-foreground">
                      <div>keep-last: {p.retention_keep_last}</div>
                      <div>keep-daily: {p.retention_keep_daily}</div>
                      <div>keep-weekly: {p.retention_keep_weekly}</div>
                      <div>keep-monthly: {p.retention_keep_monthly}</div>
                      <div>keep-yearly: {p.retention_keep_yearly}</div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5 whitespace-normal">
                      <div className="font-mono break-all text-foreground">
                        {p.backup_paths.join(", ")}
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        Last Run:{" "}
                        {p.last_run_at
                          ? new Date(p.last_run_at).toLocaleString()
                          : "Never"}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => openResticProfileModal(p)}
                          aria-label={`resticprofile for ${p.asset_tag}`}
                        >
                          <Code2
                            data-icon="inline-start"
                            aria-hidden="true"
                          />
                          resticprofile
                        </Button>
                        {currentUser.role !== "Auditor" && (
                          <>
                            <Button
                              variant="emerald"
                              size="xs"
                              disabled={runningPolicyId === p.id}
                              onClick={() => handleRunBackupNow(p)}
                            >
                              {runningPolicyId === p.id ? (
                                <Spinner data-icon="inline-start" />
                              ) : (
                                <Play
                                  data-icon="inline-start"
                                  aria-hidden="true"
                                />
                              )}
                              Run Backup Now
                            </Button>
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() =>
                                assetObj && openModalForAsset(assetObj, p)
                              }
                            >
                              <Edit3
                                data-icon="inline-start"
                                aria-hidden="true"
                              />
                              Edit Schedule
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Create / Edit Backup Policy Modal */}
      <ModalDialog
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Configure Restic Backup Schedule, Paths & Retention Policy"
        maxWidthClass="max-w-3xl"
      >
        <form onSubmit={handleSavePolicy} className="flex flex-col gap-4">
          {errorMsg && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden="true" />
              <AlertTitle>Validation Error</AlertTitle>
              <AlertDescription>{errorMsg}</AlertDescription>
            </Alert>
          )}

          <FieldGroup className="gap-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={`${formId}-asset`}>
                  Target Equipment Asset *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-asset`}
                  name="asset_id"
                  value={selectedAssetId}
                  onChange={(e) => setSelectedAssetId(Number(e.target.value))}
                  className="w-full"
                >
                  {assets.map((a) => (
                    <NativeSelectOption key={a.id} value={a.id}>
                      {a.asset_tag} — {a.name} (
                      {a.is_gmp ? "GMP" : "Non-GMP"} / {a.criticality})
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel htmlFor={`${formId}-repo`}>
                  Target Restic Storage Repository *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-repo`}
                  name="repository_id"
                  value={selectedRepoId}
                  onChange={(e) => setSelectedRepoId(Number(e.target.value))}
                  className="w-full"
                >
                  {repos.map((r) => (
                    <NativeSelectOption key={r.id} value={r.id}>
                      {r.name} ({r.backend_type})
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
            </div>

            <FieldSet className="rounded-lg border bg-muted/40 p-3.5">
              <FieldLegend variant="label">
                Backup Execution Mechanism *
              </FieldLegend>
              <div className="flex flex-wrap gap-4">
                <FieldLabel className="cursor-pointer text-xs font-semibold">
                  <input
                    type="radio"
                    name="exec_mode"
                    checked={executionMode === "ENDPOINT_AGENT"}
                    onChange={() => setExecutionMode("ENDPOINT_AGENT")}
                    className="accent-primary"
                  />
                  Endpoint OS Agent (Windows VSS / macOS launchd / Linux
                  systemd)
                </FieldLabel>
                <FieldLabel className="cursor-pointer text-xs font-semibold">
                  <input
                    type="radio"
                    name="exec_mode"
                    checked={executionMode === "CENTRAL_GATEWAY"}
                    onChange={() => setExecutionMode("CENTRAL_GATEWAY")}
                    className="accent-primary"
                  />
                  Central Agentless Gateway (For Closed PLCs / SMB / NFS / SFTP
                  Equipment)
                </FieldLabel>
              </div>
            </FieldSet>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={`${formId}-preset`}>
                  Backup Frequency Preset *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-preset`}
                  name="schedule_preset"
                  value={schedulePreset}
                  onChange={(e) => {
                    const val = e.target
                      .value as BackupPolicy["schedule_preset"]
                    setSchedulePreset(val)
                    if (val === "HOURLY") setScheduleCron("0 * * * *")
                    if (val === "EVERY_4_HOURS")
                      setScheduleCron("0 */4 * * *")
                    if (val === "DAILY") setScheduleCron("0 2 * * *")
                    if (val === "WEEKLY") setScheduleCron("0 3 * * 0")
                  }}
                  className="w-full"
                >
                  <NativeSelectOption value="HOURLY">
                    Hourly (0 * * * *)
                  </NativeSelectOption>
                  <NativeSelectOption value="EVERY_4_HOURS">
                    Every 4 Hours (0 */4 * * *)
                  </NativeSelectOption>
                  <NativeSelectOption value="DAILY">
                    Daily at 02:00 UTC (0 2 * * *)
                  </NativeSelectOption>
                  <NativeSelectOption value="WEEKLY">
                    Weekly on Sunday (0 3 * * 0)
                  </NativeSelectOption>
                  <NativeSelectOption value="CUSTOM">
                    Custom Cron Expression
                  </NativeSelectOption>
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel htmlFor={`${formId}-cron`}>
                  Cron Expression (5-field UTC) *
                </FieldLabel>
                <Input
                  id={`${formId}-cron`}
                  name="schedule_cron"
                  type="text"
                  required
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={scheduleCron}
                  onChange={(e) => {
                    setScheduleCron(e.target.value)
                    setSchedulePreset("CUSTOM")
                  }}
                  className="font-mono"
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={`${formId}-paths`}>
                  Backup Source Paths (comma-separated) *
                </FieldLabel>
                <Input
                  id={`${formId}-paths`}
                  name="backup_paths"
                  type="text"
                  required
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={backupPathsText}
                  onChange={(e) => setBackupPathsText(e.target.value)}
                  className="font-mono"
                />
              </Field>

              <Field>
                <FieldLabel htmlFor={`${formId}-excl`}>
                  Exclude Patterns (comma-separated)
                </FieldLabel>
                <Input
                  id={`${formId}-excl`}
                  name="exclude_patterns"
                  type="text"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={excludePatternsText}
                  onChange={(e) => setExcludePatternsText(e.target.value)}
                  className="font-mono"
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Field>
                <FieldLabel htmlFor={`${formId}-rpo`}>
                  Target RPO (Hours)
                </FieldLabel>
                <Input
                  id={`${formId}-rpo`}
                  name="rpo_hours"
                  type="number"
                  min={1}
                  value={rpoHours}
                  onChange={(e) => setRpoHours(Number(e.target.value))}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-rto`}>
                  Target RTO (Hours)
                </FieldLabel>
                <Input
                  id={`${formId}-rto`}
                  name="rto_hours"
                  type="number"
                  min={1}
                  value={rtoHours}
                  onChange={(e) => setRtoHours(Number(e.target.value))}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-kd`}>Keep Daily</FieldLabel>
                <Input
                  id={`${formId}-kd`}
                  name="keep_daily"
                  type="number"
                  min={1}
                  value={keepDaily}
                  onChange={(e) => setKeepDaily(Number(e.target.value))}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-ky`}>Keep Yearly</FieldLabel>
                <Input
                  id={`${formId}-ky`}
                  name="keep_yearly"
                  type="number"
                  min={1}
                  value={keepYearly}
                  onChange={(e) => setKeepYearly(Number(e.target.value))}
                />
              </Field>
            </div>

            <Field orientation="horizontal">
              <FieldLabel className="cursor-pointer text-xs font-semibold">
                <input
                  type="checkbox"
                  name="vss_enabled"
                  checked={vssEnabled}
                  onChange={(e) => setVssEnabled(e.target.checked)}
                  className="accent-primary"
                />
                <span>
                  Enable Windows Volume Shadow Copy (
                  <code className="font-mono">--use-fs-snapshot</code>) for
                  locked files
                </span>
              </FieldLabel>
            </Field>
          </FieldGroup>

          <ESignatureFields value={esig} onChange={setEsig} />

          <Separator />

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Sign &amp; Save Backup Policy</Button>
          </div>
        </form>
      </ModalDialog>

      {/* resticprofile YAML & Validation Modal */}
      <ModalDialog
        isOpen={Boolean(profilePreview)}
        onClose={() => setProfilePreview(null)}
        title={
          profilePreview
            ? `resticprofile Configuration: ${profilePreview.profile_name}`
            : "resticprofile Configuration"
        }
        maxWidthClass="max-w-4xl"
      >
        {profilePreview && (
          <div className="flex flex-col gap-4">
            <Card size="sm" className="bg-muted/40">
              <CardContent className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <div>
                  <strong className="text-foreground">Profile Name:</strong>{" "}
                  <Badge variant="outline">{profilePreview.profile_name}</Badge>{" "}
                  &bull;{" "}
                  <strong className="text-foreground">Gateway Path:</strong>{" "}
                  <code className="font-mono text-foreground">
                    {profilePreview.gateway_profile_path}
                  </code>
                </div>
                <Badge
                  variant={profilePreview.valid ? "emerald" : "destructive"}
                >
                  {profilePreview.valid
                    ? "resticprofile Validated"
                    : "Validation Error"}
                </Badge>
              </CardContent>
            </Card>

            <div className="flex flex-wrap gap-2">
              <Button
                variant={profilePreviewTab === "yaml" ? "default" : "outline"}
                size="sm"
                onClick={() => setProfilePreviewTab("yaml")}
              >
                Declarative profiles.yaml
              </Button>
              <Button
                variant={profilePreviewTab === "show" ? "default" : "outline"}
                size="sm"
                onClick={() => setProfilePreviewTab("show")}
              >
                Resolved Output (resticprofile show)
              </Button>
            </div>

            <Separator />

            <figure className="flex flex-col gap-1.5">
              <figcaption className="text-xs font-semibold text-muted-foreground">
                {profilePreviewTab === "yaml"
                  ? "Generated resticprofile v1 YAML configuration (includes retention, VSS, and webhook telemetry):"
                  : "Verified profile resolution from resticprofile show:"}
              </figcaption>
              <pre
                tabIndex={0}
                className="max-h-96 overflow-x-auto rounded-lg border bg-muted p-4 font-mono text-xs text-foreground"
              >
                <code>
                  {profilePreviewTab === "yaml"
                    ? profilePreview.config_yaml
                    : profilePreview.show_output}
                </code>
              </pre>
            </figure>
          </div>
        )}
      </ModalDialog>
    </div>
  )
}
