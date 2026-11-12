import React, { useEffect, useId, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Cloud,
  Database,
  Lock,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"
import { apiRequest } from "../api/client"
import { ESignatureFields } from "../components/ESignatureFields"
import { ModalDialog } from "../components/ModalDialog"
import { ElectronicSignatureInput, StorageRepo, User } from "../types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"

const BACKEND_TYPES = [
  {
    value: "RESTIC_REST",
    label: "Restic REST Server (rest:http://restic-server:8000/<repo>)",
  },
  {
    value: "S3_COMPATIBLE",
    label: "AWS S3 / S3-Compatible (s3:https://s3.amazonaws.com/<bucket>)",
  },
  {
    value: "MINIO",
    label: "MinIO On-Prem S3 Object Storage (s3:http://minio:9000/<bucket>)",
  },
  {
    value: "AZURE_BLOB",
    label: "Azure Blob Storage (azure:<container>:/<prefix>)",
  },
  { value: "GCS", label: "Google Cloud Storage (gs:<bucket>:/<prefix>)" },
  {
    value: "BACKBLAZE_B2",
    label: "Backblaze B2 Cloud Storage (b2:<bucket>:<prefix>)",
  },
  {
    value: "SFTP",
    label: "SFTP / SSH Enterprise Storage (sftp:user@host:/srv/restic)",
  },
  {
    value: "LOCAL_NAS",
    label: "Local / Mounted Enterprise NAS (/app/data/repos/<vault>)",
  },
]

export const StorageView: React.FC<{ currentUser: User }> = ({
  currentUser,
}) => {
  const formId = useId()
  const [repos, setRepos] = useState<StorageRepo[]>([])
  const [busyRepoId, setBusyRepoId] = useState<number | null>(null)
  const [banner, setBanner] = useState<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [name, setName] = useState("")
  const [backendType, setBackendType] = useState("S3_COMPATIBLE")
  const [repoUri, setRepoUri] = useState(
    "s3:https://s3.us-east-1.amazonaws.com/biopharma-gmp-vault/restic"
  )
  const [password, setPassword] = useState("gmp-restic-repo-default-password")
  const [awsAccessKey, setAwsAccessKey] = useState("")
  const [awsSecretKey, setAwsSecretKey] = useState("")
  const [awsRegion, setAwsRegion] = useState("us-east-1")
  const [appendOnly, setAppendOnly] = useState(true)
  const [initializeNow, setInitializeNow] = useState(false)
  const [notes, setNotes] = useState("")
  const [esig, setEsig] = useState<ElectronicSignatureInput>({
    username: currentUser.username,
    password: "gmp-password-123",
    meaning: "Approved",
    reason:
      "Qualified new Restic storage target for 3-2-1 GxP backup architecture",
  })

  const loadRepos = async () => {
    const res = await apiRequest<StorageRepo[]>("/storage")
    setRepos(res)
  }

  useEffect(() => {
    loadRepos()
  }, [])

  const handleBackendTypeChange = (type: string) => {
    setBackendType(type)
    if (type === "RESTIC_REST")
      setRepoUri("rest:http://restic-server:8000/gmp-lab-vault")
    if (type === "MINIO")
      setRepoUri("s3:http://minio:9000/gmp-restic-bucket/vault2")
    if (type === "S3_COMPATIBLE")
      setRepoUri(
        "s3:https://s3.us-east-1.amazonaws.com/biopharma-gmp-vault/restic"
      )
    if (type === "AZURE_BLOB") setRepoUri("azure:gmp-backups:/instruments")
    if (type === "GCS") setRepoUri("gs:biopharma-gmp-archive:/restic")
    if (type === "BACKBLAZE_B2") setRepoUri("b2:biopharma-gmp-b2:restic")
    if (type === "SFTP")
      setRepoUri("sftp:backup_svc@nas.biopharma.local:/srv/restic/gmp")
    if (type === "LOCAL_NAS")
      setRepoUri("/app/data/repos/secondary_nas_vault")
  }

  const handleCreateRepo = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    const envVars: Record<string, string> = {}
    if (awsAccessKey.trim()) envVars["AWS_ACCESS_KEY_ID"] = awsAccessKey.trim()
    if (awsSecretKey.trim())
      envVars["AWS_SECRET_ACCESS_KEY"] = awsSecretKey.trim()
    if (awsRegion.trim()) envVars["AWS_DEFAULT_REGION"] = awsRegion.trim()

    try {
      await apiRequest("/storage", {
        method: "POST",
        body: JSON.stringify({
          name,
          backend_type: backendType,
          repo_uri: repoUri,
          password,
          env_vars: envVars,
          immutable_append_only: appendOnly,
          initialize_now: initializeNow,
          notes,
          esignature: esig,
        }),
      })
      setIsModalOpen(false)
      await loadRepos()
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to add storage repository")
    }
  }

  const handleInitOrCheck = async (
    repo: StorageRepo,
    action: "init" | "check"
  ) => {
    setBusyRepoId(repo.id)
    setBanner(null)
    try {
      const updated = await apiRequest<StorageRepo>(
        `/storage/${repo.id}/${action}`,
        {
          method: "POST",
        }
      )
      setBanner(
        `Repository '${updated.name}' (${action.toUpperCase()}): Status=${updated.status} — ${
          updated.last_check_output || "Completed"
        }`
      )
      await loadRepos()
    } catch (err: any) {
      setBanner(
        `Error running restic ${action} on '${repo.name}': ${err.message}`
      )
    } finally {
      setBusyRepoId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            Multi-Backend Restic Storage Repositories
          </h1>
          <p className="text-sm text-muted-foreground">
            Configure Restic REST Server (
            <code className="font-mono">--append-only</code>), AWS S3 / MinIO /
            Ceph Object Storage, Azure Blob, GCS, Backblaze B2, SFTP, and Local
            NAS vaults.
          </p>
        </div>
        {currentUser.role !== "Auditor" && (
          <Button
            onClick={() => {
              setName("Secondary-S3-GMP-Vault")
              setIsModalOpen(true)
            }}
          >
            <Plus data-icon="inline-start" aria-hidden="true" />
            Add Backup Storage Backend
          </Button>
        )}
      </div>

      {banner && (
        <Alert role="status">
          <ShieldCheck aria-hidden="true" />
          <AlertTitle>Storage Operation Result</AlertTitle>
          <AlertDescription className="font-mono text-xs whitespace-pre-wrap">
            {banner}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {repos.map((r) => (
          <Card key={r.id} className="justify-between">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {r.backend_type.includes("S3") || r.backend_type === "MINIO" ? (
                  <Cloud className="size-5 text-primary" aria-hidden="true" />
                ) : (
                  <Database
                    className="size-5 text-primary"
                    aria-hidden="true"
                  />
                )}
                <h2 className="text-base font-bold text-foreground">
                  {r.name}
                </h2>
              </CardTitle>
              <CardAction>
                <Badge variant={r.status === "HEALTHY" ? "emerald" : "amber"}>
                  {r.status}
                </Badge>
              </CardAction>
            </CardHeader>

            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">{r.backend_type}</Badge>
                {r.immutable_append_only && (
                  <Badge variant="purple">
                    <Lock data-icon="inline-start" aria-hidden="true" />
                    Immutable / Append-Only WORM
                  </Badge>
                )}
                {r.is_initialized && (
                  <Badge variant="emerald">
                    <CheckCircle2 data-icon="inline-start" aria-hidden="true" />
                    AES-256 Repo Initialized
                  </Badge>
                )}
              </div>

              <div className="rounded-lg border bg-muted/50 p-2.5 font-mono text-xs break-all text-foreground">
                {r.repo_uri}
              </div>

              {r.notes && (
                <p className="text-xs text-muted-foreground">{r.notes}</p>
              )}

              {r.last_check_output && (
                <div className="truncate font-mono text-xs text-muted-foreground">
                  Last Output: {r.last_check_output}
                </div>
              )}
            </CardContent>

            {currentUser.role !== "Auditor" && (
              <CardFooter className="justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busyRepoId === r.id}
                  onClick={() => handleInitOrCheck(r, "init")}
                >
                  {busyRepoId === r.id ? (
                    <Spinner data-icon="inline-start" />
                  ) : (
                    <RefreshCw data-icon="inline-start" aria-hidden="true" />
                  )}
                  restic init
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  disabled={busyRepoId === r.id}
                  onClick={() => handleInitOrCheck(r, "check")}
                >
                  <ShieldCheck data-icon="inline-start" aria-hidden="true" />
                  Verify Integrity (restic check)
                </Button>
              </CardFooter>
            )}
          </Card>
        ))}
      </div>

      {/* Add Storage Repo Modal */}
      <ModalDialog
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add Restic Backup Storage Target"
        maxWidthClass="max-w-2xl"
      >
        <form onSubmit={handleCreateRepo} className="flex flex-col gap-4">
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
                <FieldLabel htmlFor={`${formId}-name`}>Vault Name *</FieldLabel>
                <Input
                  id={`${formId}-name`}
                  name="name"
                  type="text"
                  required
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor={`${formId}-type`}>
                  Storage Backend Type *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-type`}
                  name="backend_type"
                  value={backendType}
                  onChange={(e) => handleBackendTypeChange(e.target.value)}
                  className="w-full"
                >
                  {BACKEND_TYPES.map((b) => (
                    <NativeSelectOption key={b.value} value={b.value}>
                      {b.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
            </div>

            <Field>
              <FieldLabel htmlFor={`${formId}-uri`}>
                Restic Repository URI (
                <code className="font-mono">RESTIC_REPOSITORY</code>) *
              </FieldLabel>
              <Input
                id={`${formId}-uri`}
                name="repo_uri"
                type="text"
                required
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                value={repoUri}
                onChange={(e) => setRepoUri(e.target.value)}
                className="font-mono"
              />
            </Field>

            <Field>
              <FieldLabel htmlFor={`${formId}-pass`}>
                Restic Repository Encryption Password (
                <code className="font-mono">RESTIC_PASSWORD</code>) *
              </FieldLabel>
              <Input
                id={`${formId}-pass`}
                name="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="font-mono"
              />
            </Field>

            {(backendType === "S3_COMPATIBLE" || backendType === "MINIO") && (
              <div className="grid grid-cols-1 gap-3 rounded-lg border bg-muted/40 p-3 sm:grid-cols-3">
                <Field>
                  <FieldLabel htmlFor={`${formId}-ak`}>
                    AWS_ACCESS_KEY_ID
                  </FieldLabel>
                  <Input
                    id={`${formId}-ak`}
                    name="aws_access_key"
                    type="text"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    value={awsAccessKey}
                    onChange={(e) => setAwsAccessKey(e.target.value)}
                    className="font-mono text-xs"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor={`${formId}-sk`}>
                    AWS_SECRET_ACCESS_KEY
                  </FieldLabel>
                  <Input
                    id={`${formId}-sk`}
                    name="aws_secret_key"
                    type="password"
                    autoComplete="new-password"
                    value={awsSecretKey}
                    onChange={(e) => setAwsSecretKey(e.target.value)}
                    className="font-mono text-xs"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor={`${formId}-reg`}>
                    AWS_DEFAULT_REGION
                  </FieldLabel>
                  <Input
                    id={`${formId}-reg`}
                    name="aws_region"
                    type="text"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    value={awsRegion}
                    onChange={(e) => setAwsRegion(e.target.value)}
                    className="font-mono text-xs"
                  />
                </Field>
              </div>
            )}

            <div className="flex flex-wrap gap-4">
              <FieldLabel className="cursor-pointer text-xs font-semibold">
                <input
                  type="checkbox"
                  name="append_only"
                  checked={appendOnly}
                  onChange={(e) => setAppendOnly(e.target.checked)}
                  className="accent-primary"
                />
                <span>
                  Immutable / Append-Only Mode (Prevents snapshot pruning or
                  deletion)
                </span>
              </FieldLabel>

              <FieldLabel className="cursor-pointer text-xs font-semibold">
                <input
                  type="checkbox"
                  name="init_now"
                  checked={initializeNow}
                  onChange={(e) => setInitializeNow(e.target.checked)}
                  className="accent-primary"
                />
                <span>
                  Run <code className="font-mono">restic init</code> immediately
                  upon save
                </span>
              </FieldLabel>
            </div>

            <Field>
              <FieldLabel htmlFor={`${formId}-notes`}>
                Qualification &amp; Architecture Notes
              </FieldLabel>
              <Input
                id={`${formId}-notes`}
                name="notes"
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Off-site S3 bucket with 7-year Object Lock Compliance retention"
              />
            </Field>
          </FieldGroup>

          <ESignatureFields value={esig} onChange={setEsig} />

          <Separator />

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Sign &amp; Save Storage Vault</Button>
          </div>
        </form>
      </ModalDialog>
    </div>
  )
}
