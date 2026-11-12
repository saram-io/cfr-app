import React, { useEffect, useId, useState } from "react"
import {
  CheckCircle2,
  Download,
  FileSignature,
  ShieldCheck,
} from "lucide-react"
import { apiRequest } from "../api/client"
import { AuditLogEntry } from "../types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
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

interface ChainVerifyResult {
  valid: boolean
  total_records: number
  head_hash: string
  broken_links: unknown[]
  verified_at: string
}

export const AuditTrailView: React.FC = () => {
  const captionId = useId()
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [verification, setVerification] = useState<ChainVerifyResult | null>(
    null
  )
  const [verifying, setVerifying] = useState(false)

  const loadLogs = async () => {
    const [entries, ver] = await Promise.all([
      apiRequest<AuditLogEntry[]>("/audit"),
      apiRequest<ChainVerifyResult>("/audit/verify"),
    ])
    setLogs(entries)
    setVerification(ver)
  }

  useEffect(() => {
    loadLogs()
  }, [])

  const handleRunVerify = async () => {
    setVerifying(true)
    try {
      const ver = await apiRequest<ChainVerifyResult>("/audit/verify")
      setVerification(ver)
    } finally {
      setVerifying(false)
    }
  }

  const handleExportJson = () => {
    const blob = new Blob([JSON.stringify({ verification, logs }, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `cfr_part11_audit_trail_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            21 CFR Part 11 Cryptographic Hash-Chained Audit Trail
          </h1>
          <p className="text-sm text-muted-foreground">
            Immutable, computer-generated, time-stamped record of all asset,
            backup schedule, storage, and restore verification events with
            SHA-256 tamper detection.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="emerald"
            disabled={verifying}
            onClick={handleRunVerify}
          >
            {verifying ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <ShieldCheck data-icon="inline-start" aria-hidden="true" />
            )}
            {verifying ? "Verifying Chain..." : "Verify SHA-256 Chain Integrity"}
          </Button>
          <Button variant="outline" onClick={handleExportJson}>
            <Download data-icon="inline-start" aria-hidden="true" />
            Export Inspection Package (JSON)
          </Button>
        </div>
      </div>

      {verification && (
        <Alert
          variant={verification.valid ? "default" : "destructive"}
          className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"
        >
          <div className="flex items-start gap-2.5 text-xs">
            <CheckCircle2
              className="mt-0.5 size-5 shrink-0 text-primary"
              aria-hidden="true"
            />
            <div className="flex flex-col gap-0.5">
              <AlertTitle className="font-bold text-foreground">
                Cryptographic Chain Verification:{" "}
                {verification.valid
                  ? "PASSED (100% Intact & Tamper-Free)"
                  : "BROKEN"}
              </AlertTitle>
              <AlertDescription className="font-mono text-xs">
                Records Verified: {verification.total_records} &bull; Head Hash:{" "}
                {verification.head_hash.slice(0, 24)}...
              </AlertDescription>
            </div>
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            Verified UTC: {new Date(verification.verified_at).toLocaleString()}
          </div>
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
              21 CFR Part 11 Immutable Audit Trail
            </TableCaption>
            <TableHeader className="bg-muted/60 tracking-wider uppercase">
              <TableRow>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Seq &amp; Timestamp (UTC)
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Actor &amp; Role
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Action &amp; Entity
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Summary &amp; Reason for Change
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  21 CFR Part 11 E-Signature &amp; Hash
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l) => (
                <TableRow key={l.id}>
                  <TableHead
                    scope="row"
                    className="border-r px-4 py-3 font-normal"
                  >
                    <div className="font-mono font-bold text-foreground">
                      #{l.id}
                    </div>
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {new Date(l.timestamp).toISOString()}
                    </div>
                  </TableHead>
                  <TableCell className="px-4 py-3">
                    <div className="font-semibold text-foreground">
                      {l.actor_username}
                    </div>
                    <Badge variant="secondary" className="mt-1">
                      {l.actor_role}
                    </Badge>
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <Badge variant="sky">{l.action}</Badge>
                    <div className="mt-1 font-mono text-muted-foreground">
                      {l.entity_type}: {l.entity_id}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-md px-4 py-3 whitespace-normal">
                    <div className="font-medium text-foreground">
                      {l.summary}
                    </div>
                    {l.reason && (
                      <div className="mt-1 text-primary">
                        <strong>Reason:</strong> {l.reason}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="px-4 py-3 font-mono text-[11px]">
                    {l.signature_verified && (
                      <div className="mb-1">
                        <Badge variant="purple">
                          <FileSignature
                            data-icon="inline-start"
                            aria-hidden="true"
                          />
                          E-Signed ({l.signature_meaning})
                        </Badge>
                      </div>
                    )}
                    <div className="text-muted-foreground">
                      Prev: {l.previous_hash.slice(0, 12)}...
                    </div>
                    <div className="font-semibold text-foreground">
                      Hash: {l.record_hash.slice(0, 12)}...
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  )
}
