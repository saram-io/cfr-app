import React, { useEffect, useState } from "react"
import {
  Activity,
  AlertTriangle,
  Archive,
  CheckCircle2,
  Database,
  FileCheck,
  HardDrive,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react"
import { apiRequest } from "../api/client"
import { CriticalityBadge, GmpBadge } from "../components/StatusBadges"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"

interface DashboardSummary {
  kpis: {
    total_assets: number
    gmp_assets: number
    critical_assets: number
    compliant_assets: number
    at_risk_assets: number
    non_compliant_assets: number
    exempt_assets: number
    compliance_score_pct: number
    total_repositories: number
    healthy_repositories: number
    total_snapshots: number
    total_audit_records: number
  }
  alerts: Array<{
    asset_id: number
    asset_tag: string
    asset_name: string
    is_gmp: boolean
    criticality: string
    severity: "HIGH" | "MEDIUM"
    message: string
  }>
  recent_jobs: Array<{
    id: number
    asset_tag: string
    asset_name: string
    status: string
    triggered_by: string
    execution_mode: string
    snapshot_id?: string | null
    bytes_added: number
    duration_seconds: number
    started_at: string
  }>
  recent_drills: Array<{
    id: number
    asset_tag: string
    snapshot_id: string
    restore_type: string
    status: string
    actual_rto_minutes: number
    target_rto_minutes: number
    checksum_verified: boolean
    executed_by: string
    qa_signed_by?: string | null
    started_at: string
  }>
}

export const DashboardView: React.FC<{ onNavigate: (tab: string) => void }> = ({
  onNavigate,
}) => {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiRequest<DashboardSummary>("/dashboard/summary")
      setData(res)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading || !data) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-3 py-12 text-sm text-muted-foreground">
          <Spinner className="size-5 text-primary" />
          <span>Loading GxP Compliance Dashboard...</span>
        </CardContent>
      </Card>
    )
  }

  const { kpis, alerts, recent_jobs, recent_drills } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            Life Science GxP Asset &amp; Restic Backup Compliance Overview
          </h1>
          <p className="text-sm text-muted-foreground">
            Real-time FDA 21 CFR Part 11 / EU GMP Annex 11 backup coverage,
            RPO/RTO tracking, and SOP restore verification status.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => onNavigate("policies")}>
            <Activity data-icon="inline-start" aria-hidden="true" />
            Manage Backup Schedules
          </Button>
          <Button variant="outline" onClick={() => onNavigate("snapshots")}>
            <RotateCcw data-icon="inline-start" aria-hidden="true" />
            Run Restore Drill
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card size="sm">
          <CardHeader>
            <CardDescription className="text-xs font-semibold tracking-wider uppercase">
              Regulated Compliance Score
            </CardDescription>
            <CardAction>
              <ShieldCheck className="size-5 text-primary" aria-hidden="true" />
            </CardAction>
            <CardTitle className="flex items-baseline gap-2 text-3xl font-extrabold">
              <span>{kpis.compliance_score_pct}%</span>
              <span className="text-xs font-normal text-muted-foreground">
                ({kpis.compliant_assets} Compliant / {kpis.at_risk_assets} At
                Risk / {kpis.non_compliant_assets} Non-Compliant)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Enforces Backup Policy + Approved SOP + RPO + Restore Drill
            </p>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardDescription className="text-xs font-semibold tracking-wider uppercase">
              Lab Equipment Inventory
            </CardDescription>
            <CardAction>
              <HardDrive className="size-5 text-primary" aria-hidden="true" />
            </CardAction>
            <CardTitle className="flex flex-wrap items-baseline gap-2 text-3xl font-extrabold">
              <span>{kpis.total_assets}</span>
              <Badge variant="purple">{kpis.gmp_assets} GMP</Badge>
              <Badge variant="destructive">
                {kpis.critical_assets} Critical
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Tracks Windows, macOS, Linux &amp; Agentless PLC/Legacy systems
            </p>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardDescription className="text-xs font-semibold tracking-wider uppercase">
              Restic Snapshots &amp; Vaults
            </CardDescription>
            <CardAction>
              <Database className="size-5 text-primary" aria-hidden="true" />
            </CardAction>
            <CardTitle className="flex items-baseline gap-2 text-3xl font-extrabold">
              <span>{kpis.total_snapshots}</span>
              <span className="text-xs font-normal text-muted-foreground">
                across {kpis.total_repositories} storage targets (
                {kpis.healthy_repositories} initialized)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Restic REST (--append-only), S3/MinIO, Azure, B2 &amp; NAS
            </p>
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader>
            <CardDescription className="text-xs font-semibold tracking-wider uppercase">
              21 CFR Part 11 Audit Chain
            </CardDescription>
            <CardAction>
              <FileCheck className="size-5 text-primary" aria-hidden="true" />
            </CardAction>
            <CardTitle className="flex items-baseline gap-2 text-3xl font-extrabold">
              <span>{kpis.total_audit_records}</span>
              <Badge variant="emerald">SHA-256 Verified</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Immutable hash-chained log with E-Signature attribution
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Compliance Watchdog Alerts */}
      <Card>
        <CardHeader className="border-b bg-muted/30">
          <CardTitle>
            <h2 className="flex items-center gap-2 text-base font-bold text-foreground">
              <ShieldAlert
                className="size-5 text-destructive"
                aria-hidden="true"
              />
              Active GxP Backup &amp; Restore Compliance Watchdog Alerts (
              {alerts.length})
            </h2>
          </CardTitle>
          <CardAction>
            <Button
              variant="link"
              size="xs"
              onClick={() => onNavigate("assets")}
            >
              View Asset Criticality Matrix &rarr;
            </Button>
          </CardAction>
        </CardHeader>

        <CardContent className="flex flex-col gap-3">
          {alerts.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <CheckCircle2 aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle>All GxP Assets Compliant</EmptyTitle>
                <EmptyDescription>
                  All Critical and GMP regulated assets have active backup
                  policies, snapshots within RPO, and QA-signed SOP Restore
                  Verification Drills.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            alerts.map((al, idx) => (
              <Alert
                key={`${al.asset_tag}-${idx}`}
                variant={al.severity === "HIGH" ? "destructive" : "default"}
                className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"
              >
                <div className="flex items-start gap-3">
                  {al.severity === "HIGH" ? (
                    <ShieldAlert
                      className="mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                  ) : (
                    <AlertTriangle
                      className="mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  <div className="flex flex-col gap-1">
                    <AlertTitle className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-foreground">
                        {al.asset_tag}
                      </span>
                      <span className="text-sm font-semibold text-foreground">
                        {al.asset_name}
                      </span>
                      <GmpBadge isGmp={al.is_gmp} />
                      <CriticalityBadge criticality={al.criticality} />
                    </AlertTitle>
                    <AlertDescription>{al.message}</AlertDescription>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      onNavigate(
                        al.message.includes("Restore")
                          ? "snapshots"
                          : "policies"
                      )
                    }
                  >
                    {al.message.includes("Restore")
                      ? "Review / Sign Restore Drill"
                      : "Configure Policy"}
                  </Button>
                </div>
              </Alert>
            ))
          )}
        </CardContent>
      </Card>

      {/* Recent Backup Jobs & Recent Restore Drills */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b bg-muted/30">
            <CardTitle>
              <h2 className="flex items-center gap-2 text-base font-bold text-foreground">
                <Archive className="size-4 text-primary" aria-hidden="true" />
                Recent Restic Backup Executions
              </h2>
            </CardTitle>
            <CardAction>
              <Button
                variant="link"
                size="xs"
                onClick={() => onNavigate("snapshots")}
              >
                All Snapshots &rarr;
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-xs">
            {recent_jobs.map((j, idx) => (
              <div key={j.id} className="flex flex-col gap-3">
                {idx > 0 && <Separator />}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex flex-col gap-0.5">
                    <div className="font-semibold text-foreground">
                      <span className="font-mono">{j.asset_tag}</span> &mdash;{" "}
                      {j.asset_name}
                    </div>
                    <div className="text-muted-foreground">
                      Mode: {j.execution_mode} | Snapshot:{" "}
                      <code className="font-mono text-foreground">
                        {j.snapshot_id ? j.snapshot_id.slice(0, 8) : "N/A"}
                      </code>{" "}
                      | Duration: {j.duration_seconds}s
                    </div>
                  </div>
                  <Badge
                    variant={
                      j.status === "COMPLETED" ? "emerald" : "destructive"
                    }
                  >
                    {j.status}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b bg-muted/30">
            <CardTitle>
              <h2 className="flex items-center gap-2 text-base font-bold text-foreground">
                <RotateCcw className="size-4 text-primary" aria-hidden="true" />
                Recent SOP Restore Verification Drills
              </h2>
            </CardTitle>
            <CardAction>
              <Button
                variant="link"
                size="xs"
                onClick={() => onNavigate("snapshots")}
              >
                Manage Drills &rarr;
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-xs">
            {recent_drills.map((d, idx) => (
              <div key={d.id} className="flex flex-col gap-3">
                {idx > 0 && <Separator />}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex flex-col gap-0.5">
                    <div className="font-semibold text-foreground">
                      <span className="font-mono">{d.asset_tag}</span> &mdash;
                      Snapshot{" "}
                      <code className="font-mono">
                        {d.snapshot_id.slice(0, 8)}
                      </code>
                    </div>
                    <div className="text-muted-foreground">
                      Actual RTO: {d.actual_rto_minutes}m (Target: &le;
                      {d.target_rto_minutes}m) |{" "}
                      {d.qa_signed_by
                        ? `Signed: ${d.qa_signed_by}`
                        : "Awaiting QA E-Signature"}
                    </div>
                  </div>
                  <Badge
                    variant={d.status === "QA_APPROVED" ? "emerald" : "amber"}
                  >
                    {d.status === "QA_APPROVED"
                      ? "QA APPROVED"
                      : "PENDING QA SIGN-OFF"}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
