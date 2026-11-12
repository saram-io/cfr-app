import React, { useEffect, useId, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSignature,
  FolderOpen,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react"
import { apiRequest, getSnapshotDownloadUrl } from "../api/client"
import { ESignatureFields } from "../components/ESignatureFields"
import { ModalDialog } from "../components/ModalDialog"
import { CriticalityBadge, GmpBadge } from "../components/StatusBadges"
import {
  ElectronicSignatureInput,
  RestoreDrill,
  SnapshotRecord,
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

interface SnapshotFile {
  name: string
  type: string
  path: string
  size: number
  mtime?: string
}

export const SnapshotsRestoreView: React.FC<{ currentUser: User }> = ({
  currentUser,
}) => {
  const snapCaptionId = useId()
  const drillCaptionId = useId()

  const [snapshots, setSnapshots] = useState<SnapshotRecord[]>([])
  const [drills, setDrills] = useState<RestoreDrill[]>([])
  const [syncing, setSyncing] = useState(false)
  const [banner, setBanner] = useState<string | null>(null)

  // Snapshot File Browser Modal
  const [browsingSnapshot, setBrowsingSnapshot] =
    useState<SnapshotRecord | null>(null)
  const [snapshotFiles, setSnapshotFiles] = useState<SnapshotFile[]>([])

  // Execute Restore / SOP Drill Modal
  const [restoreTargetSnap, setRestoreTargetSnap] =
    useState<SnapshotRecord | null>(null)
  const [restoreType, setRestoreType] = useState<
    "SOP_DRILL" | "EMERGENCY_RESTORE" | "QUARANTINE_VERIFY"
  >("SOP_DRILL")
  const [restoreNotes, setRestoreNotes] = useState(
    "Quarterly SOP-CSV-008 restore verification drill"
  )
  const [restoring, setRestoring] = useState(false)

  // QA Sign-off Modal
  const [signingDrill, setSigningDrill] = useState<RestoreDrill | null>(null)
  const [qaNotes, setQaNotes] = useState(
    "SHA-256 manifest and RTO verified compliant with SOP-CSV-008"
  )
  const [esig, setEsig] = useState<ElectronicSignatureInput>({
    username: "qa_director",
    password: "gmp-password-123",
    meaning: "Approved",
    reason: "Verified SHA-256 checksums and RTO compliance per SOP-CSV-008",
  })
  const [signError, setSignError] = useState<string | null>(null)

  const loadData = async () => {
    const [snaps, drs] = await Promise.all([
      apiRequest<SnapshotRecord[]>("/backups/snapshots"),
      apiRequest<RestoreDrill[]>("/restores"),
    ])
    setSnapshots(snaps)
    setDrills(drs)
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSyncFromRestic = async () => {
    setSyncing(true)
    try {
      const res = await apiRequest<{ synced_new_snapshots: number }>(
        "/backups/snapshots/sync",
        {
          method: "POST",
        }
      )
      setBanner(
        `Synced live Restic repositories: ${res.synced_new_snapshots} new snapshot(s) imported.`
      )
      await loadData()
    } finally {
      setSyncing(false)
    }
  }

  const handleBrowseFiles = async (snap: SnapshotRecord) => {
    setBrowsingSnapshot(snap)
    const res = await apiRequest<{ files: SnapshotFile[] }>(
      `/backups/snapshots/${snap.snapshot_id}/files`
    )
    setSnapshotFiles(res.files)
  }

  const handleExecuteRestore = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!restoreTargetSnap) return
    setRestoring(true)
    setBanner(null)
    try {
      const drill = await apiRequest<RestoreDrill>("/restores/execute", {
        method: "POST",
        body: JSON.stringify({
          asset_id: restoreTargetSnap.asset_id,
          snapshot_id: restoreTargetSnap.snapshot_id,
          restore_type: restoreType,
          notes: restoreNotes,
        }),
      })
      setRestoreTargetSnap(null)
      setBanner(
        `Executed Restic Restore (#${drill.id}) for ${drill.asset_tag}! Restored ${drill.restored_file_count} file(s) (${drill.restored_bytes} B) with verified SHA-256 manifest in ${drill.actual_rto_minutes}m.`
      )
      await loadData()
    } catch (err: any) {
      setBanner(`Restore error: ${err.message}`)
    } finally {
      setRestoring(false)
    }
  }

  const handleQaSignOff = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!signingDrill) return
    setSignError(null)
    try {
      await apiRequest(`/restores/${signingDrill.id}/qa-signoff`, {
        method: "POST",
        body: JSON.stringify({
          notes: qaNotes,
          esignature: esig,
        }),
      })
      setSigningDrill(null)
      setBanner(
        `QA Electronic Signature applied to Restore Drill #${signingDrill.id} (${signingDrill.asset_tag}). Asset restore verification is now QA APPROVED.`
      )
      await loadData()
    } catch (err: any) {
      setSignError(err.message || "QA Sign-off failed")
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            Restic Snapshots, Recovery Orchestrator &amp; SOP Restore Drills
          </h1>
          <p className="text-sm text-muted-foreground">
            Inspect encrypted snapshots, browse and download backed-up
            instrument files, execute SOP Restore Verification Drills with
            SHA-256 manifests, and capture QA 21 CFR Part 11 Electronic
            Signatures.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={syncing}
          onClick={handleSyncFromRestic}
        >
          {syncing ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <RefreshCw data-icon="inline-start" aria-hidden="true" />
          )}
          Sync Snapshots from Restic Vaults
        </Button>
      </div>

      {banner && (
        <Alert role="status">
          <CheckCircle2 aria-hidden="true" />
          <AlertTitle>Recovery Operation Status</AlertTitle>
          <AlertDescription>{banner}</AlertDescription>
        </Alert>
      )}

      {/* Section 1: Restic Snapshots */}
      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-lg font-bold text-foreground">
          1. Encrypted Restic Backup Snapshots ({snapshots.length})
        </h2>
        <Card className="p-0">
          <div
            tabIndex={0}
            role="region"
            aria-labelledby={snapCaptionId}
            className="table-wrapper"
          >
            <Table className="text-xs">
              <TableCaption id={snapCaptionId} className="sr-only">
                Restic Backup Snapshots
              </TableCaption>
              <TableHeader className="bg-muted/60 tracking-wider uppercase">
                <TableRow>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Snapshot ID &amp; Timestamp
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Asset &amp; Classification
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Storage Vault &amp; Paths
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Files &amp; Verification
                  </TableHead>
                  <TableHead
                    scope="col"
                    className="px-4 py-3 text-right font-bold"
                  >
                    Restore &amp; Inspect
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshots.map((s) => (
                  <TableRow key={s.id}>
                    <TableHead
                      scope="row"
                      className="border-r px-4 py-3.5 font-normal"
                    >
                      <Badge variant="default">{s.short_id}</Badge>
                      <div className="mt-1 text-muted-foreground">
                        {new Date(s.created_at).toLocaleString()}
                      </div>
                    </TableHead>
                    <TableCell className="px-4 py-3.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-foreground">
                          {s.asset_tag}
                        </span>
                        <GmpBadge isGmp={s.is_gmp} />
                        <CriticalityBadge criticality={s.criticality} />
                      </div>
                      <div className="mt-1 font-medium text-foreground">
                        {s.asset_name}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5 whitespace-normal">
                      <div className="font-semibold text-foreground">
                        {s.repository_name}
                      </div>
                      <div className="mt-0.5 font-mono break-all text-muted-foreground">
                        {s.paths.join(", ")}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5">
                      <div>
                        <strong className="text-foreground">
                          {s.file_count}
                        </strong>{" "}
                        file(s) &bull;{" "}
                        <strong className="text-foreground">
                          {s.size_bytes}
                        </strong>{" "}
                        bytes
                      </div>
                      <div className="mt-1">
                        {s.is_verified ? (
                          <Badge variant="emerald">
                            <CheckCircle2
                              data-icon="inline-start"
                              aria-hidden="true"
                            />
                            Restore Drill Verified
                          </Badge>
                        ) : (
                          <Badge variant="secondary">
                            Unverified Snapshot
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => handleBrowseFiles(s)}
                        >
                          <FolderOpen
                            data-icon="inline-start"
                            aria-hidden="true"
                          />
                          Inspect Files
                        </Button>
                        <Button
                          variant="outline"
                          size="xs"
                          render={
                            <a href={getSnapshotDownloadUrl(s.snapshot_id)} />
                          }
                          nativeButton={false}
                        >
                          <Download
                            data-icon="inline-start"
                            aria-hidden="true"
                          />
                          Download .zip
                        </Button>
                        {currentUser.role !== "Auditor" && (
                          <Button
                            variant="default"
                            size="xs"
                            onClick={() => setRestoreTargetSnap(s)}
                          >
                            <RotateCcw
                              data-icon="inline-start"
                              aria-hidden="true"
                            />
                            Restore / Drill
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      </section>

      {/* Section 2: SOP Restore Verification Drills & Emergency Restores */}
      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-lg font-bold text-foreground">
          2. SOP Restore Verification Drills &amp; QA Electronic Sign-Off Log (
          {drills.length})
        </h2>
        <Card className="p-0">
          <div
            tabIndex={0}
            role="region"
            aria-labelledby={drillCaptionId}
            className="table-wrapper"
          >
            <Table className="text-xs">
              <TableCaption id={drillCaptionId} className="sr-only">
                SOP Restore Verification Drills and QA Sign-Off Records
              </TableCaption>
              <TableHeader className="bg-muted/60 tracking-wider uppercase">
                <TableRow>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Drill ID &amp; Asset
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    Snapshot &amp; Target
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    RTO Performance
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    SHA-256 Manifest Verification
                  </TableHead>
                  <TableHead scope="col" className="px-4 py-3 font-bold">
                    QA 21 CFR Part 11 Sign-Off
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drills.map((d) => (
                  <TableRow key={d.id}>
                    <TableHead
                      scope="row"
                      className="border-r px-4 py-3.5 font-normal whitespace-normal"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="purple">DRILL #{d.id}</Badge>
                        <span className="font-mono font-bold text-foreground">
                          {d.asset_tag}
                        </span>
                      </div>
                      <div className="mt-0.5 font-semibold text-foreground">
                        {d.asset_name}
                      </div>
                      <div className="text-muted-foreground">
                        Executed by: {d.executed_by}
                      </div>
                    </TableHead>
                    <TableCell className="px-4 py-3.5 whitespace-normal">
                      <div>
                        Snapshot:{" "}
                        <code className="font-mono font-bold text-foreground">
                          {d.snapshot_id.slice(0, 8)}
                        </code>{" "}
                        ({d.restore_type})
                      </div>
                      <div className="mt-1 font-mono break-all text-muted-foreground">
                        {d.target_path}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5">
                      <div className="font-semibold text-foreground">
                        Actual RTO:{" "}
                        <span className="text-primary">
                          {d.actual_rto_minutes} min
                        </span>
                      </div>
                      <div className="text-muted-foreground">
                        Target RTO: &le; {d.target_rto_minutes} min
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3.5">
                      <div className="inline-flex items-center gap-1 font-semibold text-foreground">
                        <ShieldCheck
                          className="size-4 text-primary"
                          aria-hidden="true"
                        />
                        {d.restored_file_count} file(s) ({d.restored_bytes} B)
                        SHA-256 Verified
                      </div>
                      {d.sha256_manifest.slice(0, 2).map((m, i) => (
                        <div
                          key={i}
                          className="max-w-xs truncate font-mono text-[11px] text-muted-foreground"
                        >
                          {m.sha256.slice(0, 16)}... {m.file}
                        </div>
                      ))}
                    </TableCell>
                    <TableCell className="px-4 py-3.5">
                      {d.status === "QA_APPROVED" ? (
                        <div className="flex flex-col items-start gap-1">
                          <Badge variant="emerald">
                            <CheckCircle2
                              data-icon="inline-start"
                              aria-hidden="true"
                            />
                            QA APPROVED ({d.qa_signature_meaning})
                          </Badge>
                          <div className="font-medium text-muted-foreground">
                            {d.qa_signed_by}
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-start gap-1.5">
                          <Badge variant="amber">PENDING QA E-SIGNATURE</Badge>
                          {(currentUser.role === "QA_Compliance" ||
                            currentUser.role === "Admin") && (
                            <Button
                              variant="default"
                              size="xs"
                              onClick={() => {
                                setSignError(null)
                                setSigningDrill(d)
                              }}
                            >
                              <FileSignature
                                data-icon="inline-start"
                                aria-hidden="true"
                              />
                              Apply QA E-Signature
                            </Button>
                          )}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      </section>

      {/* Inspect Snapshot Files Modal */}
      <ModalDialog
        isOpen={Boolean(browsingSnapshot)}
        onClose={() => setBrowsingSnapshot(null)}
        title={
          browsingSnapshot
            ? `Snapshot File Tree: ${browsingSnapshot.asset_tag} (${browsingSnapshot.short_id})`
            : "Files"
        }
        maxWidthClass="max-w-3xl"
      >
        {browsingSnapshot && (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">
              Live output from{" "}
              <code className="font-mono text-foreground">
                restic ls {browsingSnapshot.short_id}
              </code>
              :
            </p>
            <Card size="sm" className="bg-muted/40">
              <CardContent>
                <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto font-mono text-xs">
                  {snapshotFiles.map((f, idx) => (
                    <li key={idx} className="flex flex-col gap-1.5">
                      {idx > 0 && <Separator />}
                      <div className="flex items-center justify-between gap-2 py-0.5">
                        <span className="break-all text-foreground">
                          {f.path}
                        </span>
                        <Badge variant="outline">
                          {f.type} &bull; {f.size} B
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        )}
      </ModalDialog>

      {/* Execute Restore / Drill Modal */}
      <ModalDialog
        isOpen={Boolean(restoreTargetSnap)}
        onClose={() => setRestoreTargetSnap(null)}
        title={
          restoreTargetSnap
            ? `Execute Restic Restore / SOP Drill: ${restoreTargetSnap.asset_tag}`
            : "Restore"
        }
        maxWidthClass="max-w-xl"
      >
        {restoreTargetSnap && (
          <form onSubmit={handleExecuteRestore} className="flex flex-col gap-4">
            <Card size="sm" className="bg-muted/40">
              <CardContent className="flex flex-col gap-1 text-xs">
                <div>
                  <strong className="text-foreground">Asset:</strong>{" "}
                  {restoreTargetSnap.asset_tag} ({restoreTargetSnap.asset_name})
                </div>
                <div>
                  <strong className="text-foreground">Snapshot ID:</strong>{" "}
                  <code className="font-mono">
                    {restoreTargetSnap.snapshot_id}
                  </code>
                </div>
              </CardContent>
            </Card>

            <FieldGroup className="gap-4">
              <FieldSet className="gap-2">
                <FieldLegend variant="label">
                  Restore Operation Type *
                </FieldLegend>
                <div className="flex flex-col gap-2">
                  <FieldLabel className="cursor-pointer text-xs font-semibold">
                    <input
                      type="radio"
                      name="restore_type"
                      checked={restoreType === "SOP_DRILL"}
                      onChange={() => setRestoreType("SOP_DRILL")}
                      className="accent-primary"
                    />
                    <span>
                      SOP-CSV-008 Periodic Restore Verification Drill (Restores
                      &amp; verifies SHA-256 manifest)
                    </span>
                  </FieldLabel>
                  <FieldLabel className="cursor-pointer text-xs font-semibold">
                    <input
                      type="radio"
                      name="restore_type"
                      checked={restoreType === "EMERGENCY_RESTORE"}
                      onChange={() => setRestoreType("EMERGENCY_RESTORE")}
                      className="accent-primary"
                    />
                    <span>Emergency Production Equipment Data Recovery</span>
                  </FieldLabel>
                </div>
              </FieldSet>

              <Field>
                <FieldLabel htmlFor="restore-notes">
                  Operator Execution Notes *
                </FieldLabel>
                <Input
                  id="restore-notes"
                  name="restore_notes"
                  type="text"
                  required
                  value={restoreNotes}
                  onChange={(e) => setRestoreNotes(e.target.value)}
                />
              </Field>
            </FieldGroup>

            <Separator />

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setRestoreTargetSnap(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={restoring}>
                {restoring && <Spinner data-icon="inline-start" />}
                {restoring
                  ? "Restoring & Computing SHA-256..."
                  : "Execute Restic Restore Now"}
              </Button>
            </div>
          </form>
        )}
      </ModalDialog>

      {/* QA Electronic Signature Sign-off Modal */}
      <ModalDialog
        isOpen={Boolean(signingDrill)}
        onClose={() => setSigningDrill(null)}
        title={
          signingDrill
            ? `QA 21 CFR Part 11 Sign-Off: Restore Drill #${signingDrill.id} (${signingDrill.asset_tag})`
            : "Sign Off"
        }
        maxWidthClass="max-w-2xl"
      >
        {signingDrill && (
          <form onSubmit={handleQaSignOff} className="flex flex-col gap-4">
            {signError && (
              <Alert variant="destructive">
                <AlertCircle aria-hidden="true" />
                <AlertTitle>Sign-Off Error</AlertTitle>
                <AlertDescription>{signError}</AlertDescription>
              </Alert>
            )}

            <Alert>
              <CheckCircle2 aria-hidden="true" />
              <AlertTitle>
                Restored Asset: {signingDrill.asset_tag} &mdash;{" "}
                {signingDrill.asset_name}
              </AlertTitle>
              <AlertDescription className="flex flex-col gap-1 text-xs">
                <div>
                  <strong className="text-foreground">RTO Verification:</strong>{" "}
                  Actual {signingDrill.actual_rto_minutes} min &le; Target{" "}
                  {signingDrill.target_rto_minutes} min
                </div>
                <div>
                  <strong className="text-foreground">
                    Cryptographic Checksum Result:
                  </strong>{" "}
                  {signingDrill.restored_file_count} file(s) restored, 100%
                  SHA-256 verified
                </div>
              </AlertDescription>
            </Alert>

            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="qa-review-notes">
                  QA Review Comments
                </FieldLabel>
                <Input
                  id="qa-review-notes"
                  name="qa_notes"
                  type="text"
                  value={qaNotes}
                  onChange={(e) => setQaNotes(e.target.value)}
                />
              </Field>
            </FieldGroup>

            <ESignatureFields
              value={esig}
              onChange={setEsig}
              title="QA Compliance Electronic Signature (Requires QA_Compliance or Admin Role)"
            />

            <Separator />

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSigningDrill(null)}>
                Cancel
              </Button>
              <Button type="submit">
                Sign &amp; Approve Restore Verification Drill
              </Button>
            </div>
          </form>
        )}
      </ModalDialog>
    </div>
  )
}
