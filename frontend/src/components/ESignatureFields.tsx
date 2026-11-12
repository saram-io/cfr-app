import React, { useId } from "react"
import { FileSignature } from "lucide-react"
import { ElectronicSignatureInput } from "../types"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

interface ESignatureFieldsProps {
  value: ElectronicSignatureInput
  onChange: (next: ElectronicSignatureInput) => void
  title?: string
}

const SIGNATURE_MEANINGS: Array<ElectronicSignatureInput["meaning"]> = [
  "Approved",
  "Verified",
  "Reviewed",
  "Authored",
]

export const ESignatureFields: React.FC<ESignatureFieldsProps> = ({
  value,
  onChange,
  title = "21 CFR Part 11 / EU GMP Annex 11 Electronic Signature",
}) => {
  const baseId = useId()

  return (
    <FieldSet className="mt-4 rounded-xl border bg-muted/40 p-4">
      <FieldLegend className="flex items-center gap-1.5 px-2 text-xs font-bold tracking-wider text-foreground uppercase">
        <FileSignature className="size-4 text-primary" aria-hidden="true" />
        {title}
      </FieldLegend>
      <FieldDescription className="text-xs">
        Regulated GxP state modification requires signer re-authentication,
        signature meaning, and verifiable reason for change.
      </FieldDescription>

      <FieldGroup className="gap-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor={`${baseId}-user`}>
              Signer Username *
            </FieldLabel>
            <Input
              id={`${baseId}-user`}
              name="esig_username"
              type="text"
              required
              autoComplete="username"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              value={value.username}
              onChange={(e) =>
                onChange({ ...value, username: e.target.value })
              }
              placeholder="e.g. qa_director or lab_eng"
            />
          </Field>

          <Field>
            <FieldLabel htmlFor={`${baseId}-pass`}>
              Signer Password (default:{" "}
              <code className="font-mono">gmp-password-123</code>) *
            </FieldLabel>
            <Input
              id={`${baseId}-pass`}
              name="esig_password"
              type="password"
              required
              autoComplete="current-password"
              value={value.password}
              onChange={(e) =>
                onChange({ ...value, password: e.target.value })
              }
            />
          </Field>
        </div>

        <FieldSet className="gap-1.5">
          <FieldLegend variant="label">
            Signature Meaning (21 CFR §11.50) *
          </FieldLegend>
          <div className="flex flex-wrap gap-2">
            {SIGNATURE_MEANINGS.map((m) => (
              <FieldLabel
                key={m}
                className="cursor-pointer rounded-md border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted has-[:checked]:border-primary has-[:checked]:bg-primary/10 has-[:checked]:text-primary"
              >
                <input
                  type="radio"
                  name={`${baseId}-meaning`}
                  value={m}
                  checked={value.meaning === m}
                  onChange={() => onChange({ ...value, meaning: m })}
                  className="accent-primary"
                />
                {m}
              </FieldLabel>
            ))}
          </div>
        </FieldSet>

        <Field>
          <FieldLabel htmlFor={`${baseId}-reason`}>
            Reason for Change / Approval Justification *
          </FieldLabel>
          <Input
            id={`${baseId}-reason`}
            name="esig_reason"
            type="text"
            required
            minLength={3}
            value={value.reason}
            onChange={(e) => onChange({ ...value, reason: e.target.value })}
            placeholder="e.g. Change Control CC-2026-104 or Quarterly SOP-CSV-008 Restore Verification"
          />
        </Field>
      </FieldGroup>
    </FieldSet>
  )
}
