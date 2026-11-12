import React from "react"
import {
  AlertTriangle,
  CheckCircle2,
  MinusCircle,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"

export const GmpBadge: React.FC<{ isGmp: boolean }> = ({ isGmp }) => {
  if (isGmp) {
    return (
      <Badge variant="purple">
        <ShieldCheck data-icon="inline-start" />
        GMP Regulated
      </Badge>
    )
  }
  return <Badge variant="secondary">Non-GMP (R&amp;D)</Badge>
}

export const CriticalityBadge: React.FC<{ criticality: string }> = ({
  criticality,
}) => {
  const upper = criticality.toUpperCase()
  if (upper === "CRITICAL") {
    return (
      <Badge variant="destructive">
        <ShieldAlert data-icon="inline-start" />
        CRITICAL
      </Badge>
    )
  }
  if (upper === "MAJOR") {
    return (
      <Badge variant="amber">
        <AlertTriangle data-icon="inline-start" />
        MAJOR
      </Badge>
    )
  }
  return <Badge variant="secondary">MINOR</Badge>
}

export const ComplianceBadge: React.FC<{ status: string }> = ({ status }) => {
  const upper = status.toUpperCase()
  if (upper === "COMPLIANT") {
    return (
      <Badge variant="emerald">
        <CheckCircle2 data-icon="inline-start" />
        COMPLIANT
      </Badge>
    )
  }
  if (upper === "AT_RISK") {
    return (
      <Badge variant="amber">
        <AlertTriangle data-icon="inline-start" />
        AT RISK
      </Badge>
    )
  }
  if (upper === "NON_COMPLIANT") {
    return (
      <Badge variant="destructive">
        <ShieldAlert data-icon="inline-start" />
        NON-COMPLIANT
      </Badge>
    )
  }
  return (
    <Badge variant="secondary">
      <MinusCircle data-icon="inline-start" />
      EXEMPT
    </Badge>
  )
}
