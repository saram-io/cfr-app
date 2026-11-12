import React, { useEffect, useId, useState } from "react"
import {
  AlertCircle,
  Code2,
  Edit3,
  Plus,
  Search,
  Terminal,
} from "lucide-react"
import { apiRequest } from "../api/client"
import { ESignatureFields } from "../components/ESignatureFields"
import { ModalDialog } from "../components/ModalDialog"
import {
  ComplianceBadge,
  CriticalityBadge,
  GmpBadge,
} from "../components/StatusBadges"
import { Asset, ElectronicSignatureInput, SOPDocument, User } from "../types"
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
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const EQUIPMENT_CATEGORIES = [
  "Chromatography (HPLC/UPLC)",
  "Mass Spectrometry",
  "Bioreactor / Fermenter",
  "Genomics / NGS Sequencer",
  "Flow Cytometry",
  "qPCR / Thermal Cycler",
  "Microscopy / High-Content Imaging",
  "Environmental / Freezer Monitor",
  "LIMS / ELN Database Server",
  "Benchtop Meter / Balance",
]

const OS_TYPES = [
  {
    value: "WINDOWS",
    label: "Windows Workstation / Server (Restic + VSS Agent)",
  },
  { value: "MACOS", label: "macOS Workstation (Restic + launchd Agent)" },
  { value: "LINUX", label: "Linux / Unix System (Restic + systemd Agent)" },
  {
    value: "AGENTLESS_SMB",
    label: "Agentless Equipment via Read-Only SMB/CIFS or NFS Gateway",
  },
  {
    value: "AGENTLESS_SFTP",
    label: "Agentless Equipment via SFTP / FTP Landing Zone",
  },
  {
    value: "AIRGAPPED_USB",
    label: "Air-Gapped / Cleanroom Equipment (USB Gadget or Sneaker-Net)",
  },
]

interface AgentBundle {
  asset_tag: string
  asset_name: string
  os_type: string
  agent_token: string
  schedule_cron: string
  backup_paths: string[]
  exclude_patterns: string[]
  repository_uri: string
  resticprofile_name: string
  resticprofile_yaml: string
  windows_powershell_script: string
  unix_bash_script: string
  agentless_setup_commands: string
}

export const AssetsView: React.FC<{ currentUser: User }> = ({
  currentUser,
}) => {
  const captionId = useId()
  const formId = useId()
  const [assets, setAssets] = useState<Asset[]>([])
  const [sops, setSops] = useState<SOPDocument[]>([])
  const [search, setSearch] = useState("")
  const [filterGmp, setFilterGmp] = useState<string>("ALL")
  const [filterCrit, setFilterCrit] = useState<string>("ALL")
  const [filterComp, setFilterComp] = useState<string>("ALL")

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [bundleModalAsset, setBundleModalAsset] = useState<AgentBundle | null>(
    null
  )
  const [bundleTab, setBundleTab] = useState<
    "resticprofile" | "windows" | "unix" | "agentless"
  >("windows")

  // Form fields
  const [assetTag, setAssetTag] = useState("")
  const [name, setName] = useState("")
  const [category, setCategory] = useState(EQUIPMENT_CATEGORIES[0])
  const [vendor, setVendor] = useState("")
  const [model, setModel] = useState("")
  const [serialNumber, setSerialNumber] = useState("")
  const [softwareVersion, setSoftwareVersion] = useState("")
  const [location, setLocation] = useState("")
  const [hostnameOrIp, setHostnameOrIp] = useState("")
  const [osType, setOsType] = useState("WINDOWS")
  const [isGmp, setIsGmp] = useState(true)
  const [criticality, setCriticality] = useState<
    "CRITICAL" | "MAJOR" | "MINOR"
  >("CRITICAL")
  const [systemOwner, setSystemOwner] = useState("")
  const [qaOwner, setQaOwner] = useState("Marcus Chen (QA Compliance)")
  const [sopId, setSopId] = useState<number | "">("")
  const [notes, setNotes] = useState("")
  const [esig, setEsig] = useState<ElectronicSignatureInput>({
    username: currentUser.username,
    password: "gmp-password-123",
    meaning: "Approved",
    reason: "",
  })

  const loadAssets = async () => {
    const params = new URLSearchParams()
    if (filterGmp === "GMP") params.set("is_gmp", "true")
    if (filterGmp === "NONGMP") params.set("is_gmp", "false")
    if (filterCrit !== "ALL") params.set("criticality", filterCrit)
    if (filterComp !== "ALL") params.set("compliance_status", filterComp)
    if (search.trim()) params.set("search", search.trim())

    const [assetList, sopList] = await Promise.all([
      apiRequest<Asset[]>(`/assets?${params.toString()}`),
      apiRequest<SOPDocument[]>("/sops"),
    ])
    setAssets(assetList)
    setSops(sopList)
  }

  useEffect(() => {
    loadAssets()
  }, [filterGmp, filterCrit, filterComp, search])

  const openCreateModal = () => {
    setEditingAsset(null)
    setErrorMsg(null)
    setAssetTag("HPLC-QC-007")
    setName("")
    setCategory(EQUIPMENT_CATEGORIES[0])
    setVendor("")
    setModel("")
    setSerialNumber("")
    setSoftwareVersion("")
    setLocation("Bldg A - QC Lab 201")
    setHostnameOrIp("10.20.14.120")
    setOsType("WINDOWS")
    setIsGmp(true)
    setCriticality("CRITICAL")
    setSystemOwner("Dr. Rachel Kim")
    setQaOwner("Marcus Chen (QA Compliance)")
    setSopId(sops[0]?.id ?? "")
    setNotes("")
    setEsig({
      username: currentUser.username,
      password: "gmp-password-123",
      meaning: "Approved",
      reason: "Initial GMP equipment registration per IQ/OQ protocol",
    })
    setIsModalOpen(true)
  }

  const openEditModal = (a: Asset) => {
    setEditingAsset(a)
    setErrorMsg(null)
    setAssetTag(a.asset_tag)
    setName(a.name)
    setCategory(a.category)
    setVendor(a.vendor)
    setModel(a.model)
    setSerialNumber(a.serial_number)
    setSoftwareVersion(a.software_version || "")
    setLocation(a.location)
    setHostnameOrIp(a.hostname_or_ip)
    setOsType(a.os_type)
    setIsGmp(a.is_gmp)
    setCriticality(a.criticality)
    setSystemOwner(a.system_owner)
    setQaOwner(a.qa_owner)
    setSopId(a.sop_id ?? "")
    setNotes(a.notes || "")
    setEsig({
      username: currentUser.username,
      password: "gmp-password-123",
      meaning: "Approved",
      reason: "",
    })
    setIsModalOpen(true)
  }

  const handleSaveAsset = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    const requiresEsig =
      isGmp ||
      criticality === "CRITICAL" ||
      (editingAsset &&
        (editingAsset.is_gmp || editingAsset.criticality === "CRITICAL"))
    const payload: Record<string, unknown> = {
      asset_tag: assetTag,
      name,
      category,
      vendor,
      model,
      serial_number: serialNumber,
      software_version: softwareVersion,
      location,
      hostname_or_ip: hostnameOrIp,
      os_type: osType,
      is_gmp: isGmp,
      criticality,
      system_owner: systemOwner,
      qa_owner: qaOwner,
      sop_id: sopId === "" ? null : Number(sopId),
      notes,
      esignature: requiresEsig ? esig : undefined,
    }

    try {
      if (editingAsset) {
        await apiRequest(`/assets/${editingAsset.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
      } else {
        await apiRequest("/assets", {
          method: "POST",
          body: JSON.stringify(payload),
        })
      }
      setIsModalOpen(false)
      await loadAssets()
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save asset")
    }
  }

  const openAgentBundle = async (asset: Asset) => {
    const bundle = await apiRequest<AgentBundle>(
      `/assets/${asset.id}/agent-bundle`
    )
    setBundleModalAsset(bundle)
    if (asset.os_type === "WINDOWS") setBundleTab("windows")
    else if (asset.os_type === "MACOS" || asset.os_type === "LINUX")
      setBundleTab("unix")
    else setBundleTab("agentless")
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-bold text-foreground">
            Life Science Equipment Register &amp; Criticality Matrix
          </h1>
          <p className="text-sm text-muted-foreground">
            Track GMP vs. Non-GMP status and Criticality. Any{" "}
            <strong className="text-foreground">CRITICAL</strong> or{" "}
            <strong className="text-foreground">GMP</strong> asset enforces a
            Restic backup policy, approved SOP, and periodic Restore
            Verification Drill.
          </p>
        </div>
        {currentUser.role !== "Auditor" && (
          <Button onClick={openCreateModal}>
            <Plus data-icon="inline-start" aria-hidden="true" />
            Register New Equipment
          </Button>
        )}
      </div>

      {/* Semantic <search> landmark per modern-web-guidance (html) */}
      <search>
        <Card size="sm">
          <CardContent>
            <form onSubmit={(e) => e.preventDefault()}>
              <FieldGroup className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <Field>
                  <FieldLabel htmlFor={`${formId}-q`}>
                    Search Equipment
                  </FieldLabel>
                  <InputGroup>
                    <InputGroupAddon>
                      <Search aria-hidden="true" />
                    </InputGroupAddon>
                    <InputGroupInput
                      id={`${formId}-q`}
                      name="q"
                      type="search"
                      autoCorrect="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Tag, HPLC, Sequencer, Lab..."
                    />
                  </InputGroup>
                </Field>

                <Field>
                  <FieldLabel htmlFor={`${formId}-gmp`}>
                    GMP Classification
                  </FieldLabel>
                  <NativeSelect
                    id={`${formId}-gmp`}
                    name="filter_gmp"
                    value={filterGmp}
                    onChange={(e) => setFilterGmp(e.target.value)}
                    className="w-full"
                  >
                    <NativeSelectOption value="ALL">
                      All (GMP &amp; Non-GMP)
                    </NativeSelectOption>
                    <NativeSelectOption value="GMP">
                      GMP Regulated Only
                    </NativeSelectOption>
                    <NativeSelectOption value="NONGMP">
                      Non-GMP (R&amp;D) Only
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>

                <Field>
                  <FieldLabel htmlFor={`${formId}-crit`}>
                    Criticality Tier
                  </FieldLabel>
                  <NativeSelect
                    id={`${formId}-crit`}
                    name="filter_crit"
                    value={filterCrit}
                    onChange={(e) => setFilterCrit(e.target.value)}
                    className="w-full"
                  >
                    <NativeSelectOption value="ALL">
                      All Criticality Tiers
                    </NativeSelectOption>
                    <NativeSelectOption value="CRITICAL">
                      CRITICAL (Mandatory Backup &amp; Drill)
                    </NativeSelectOption>
                    <NativeSelectOption value="MAJOR">MAJOR</NativeSelectOption>
                    <NativeSelectOption value="MINOR">MINOR</NativeSelectOption>
                  </NativeSelect>
                </Field>

                <Field>
                  <FieldLabel htmlFor={`${formId}-comp`}>
                    Compliance Watchdog Status
                  </FieldLabel>
                  <NativeSelect
                    id={`${formId}-comp`}
                    name="filter_comp"
                    value={filterComp}
                    onChange={(e) => setFilterComp(e.target.value)}
                    className="w-full"
                  >
                    <NativeSelectOption value="ALL">
                      All Statuses
                    </NativeSelectOption>
                    <NativeSelectOption value="COMPLIANT">
                      COMPLIANT
                    </NativeSelectOption>
                    <NativeSelectOption value="AT_RISK">
                      AT RISK (Drill Sign-Off Needed)
                    </NativeSelectOption>
                    <NativeSelectOption value="NON_COMPLIANT">
                      NON-COMPLIANT
                    </NativeSelectOption>
                    <NativeSelectOption value="EXEMPT">
                      EXEMPT
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </search>

      {/* Responsive Table with sticky row & column headers per modern-web-guidance (responsive-table) */}
      <Card className="p-0">
        <div
          tabIndex={0}
          role="region"
          aria-labelledby={captionId}
          className="table-wrapper"
        >
          <Table className="text-xs">
            <TableCaption id={captionId} className="sr-only">
              Life Science Equipment Register and Backup Compliance Status
            </TableCaption>
            <TableHeader className="bg-muted/60 tracking-wider uppercase">
              <TableRow>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Asset Tag &amp; Name
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  GxP &amp; Criticality
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  OS / Connection Mode
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Backup Policy &amp; SOP
                </TableHead>
                <TableHead scope="col" className="px-4 py-3 font-bold">
                  Compliance Status
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
              {assets.map((a) => (
                <TableRow key={a.id}>
                  <TableHead
                    scope="row"
                    className="border-r px-4 py-3.5 font-normal whitespace-normal"
                  >
                    <div className="font-mono text-xs font-bold text-primary">
                      {a.asset_tag}
                    </div>
                    <div className="text-sm font-semibold text-foreground">
                      {a.name}
                    </div>
                    <div className="text-muted-foreground">
                      {a.vendor} {a.model} &bull; SN: {a.serial_number} &bull;{" "}
                      {a.location}
                    </div>
                  </TableHead>
                  <TableCell className="px-4 py-3.5">
                    <div className="flex flex-col items-start gap-1.5">
                      <GmpBadge isGmp={a.is_gmp} />
                      <CriticalityBadge criticality={a.criticality} />
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3.5">
                    <Badge variant="secondary">{a.os_type}</Badge>
                    <div className="mt-1 text-muted-foreground">
                      Host: {a.hostname_or_ip}
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3.5">
                    {a.policy_schedule ? (
                      <div>
                        <div className="font-semibold text-foreground">
                          {a.policy_schedule}
                        </div>
                        <div className="text-muted-foreground">
                          Vault: {a.repository_name}
                        </div>
                      </div>
                    ) : (
                      <Badge variant="destructive">No Backup Policy</Badge>
                    )}
                    <div className="mt-1 text-muted-foreground">
                      SOP:{" "}
                      <span className="font-mono font-semibold text-foreground">
                        {a.sop_code || "Unassigned"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3.5 whitespace-normal">
                    <ComplianceBadge status={a.compliance.overall_status} />
                    {a.compliance.issues.length > 0 && (
                      <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4 text-destructive">
                        {a.compliance.issues.map((iss, i) => (
                          <li key={i}>{iss}</li>
                        ))}
                      </ul>
                    )}
                  </TableCell>
                  <TableCell className="px-4 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => openAgentBundle(a)}
                      >
                        <Terminal
                          data-icon="inline-start"
                          aria-hidden="true"
                        />
                        Restic Setup Script
                      </Button>
                      {currentUser.role !== "Auditor" && (
                        <Button
                          variant="default"
                          size="xs"
                          onClick={() => openEditModal(a)}
                        >
                          <Edit3
                            data-icon="inline-start"
                            aria-hidden="true"
                          />
                          Edit
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

      {/* Add / Edit Asset Modal */}
      <ModalDialog
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={
          editingAsset
            ? `Edit Asset ${editingAsset.asset_tag}`
            : "Register New Life Science Equipment"
        }
        maxWidthClass="max-w-3xl"
      >
        <form onSubmit={handleSaveAsset} className="flex flex-col gap-4">
          {errorMsg && (
            <Alert variant="destructive">
              <AlertCircle aria-hidden="true" />
              <AlertTitle>Validation Error</AlertTitle>
              <AlertDescription>{errorMsg}</AlertDescription>
            </Alert>
          )}

          <FieldGroup className="gap-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field>
                <FieldLabel htmlFor={`${formId}-tag`}>Asset Tag *</FieldLabel>
                <Input
                  id={`${formId}-tag`}
                  name="asset_tag"
                  type="text"
                  required
                  disabled={Boolean(editingAsset)}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={assetTag}
                  onChange={(e) => setAssetTag(e.target.value)}
                  className="font-mono"
                />
              </Field>
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor={`${formId}-name`}>
                  Equipment Name / Description *
                </FieldLabel>
                <Input
                  id={`${formId}-name`}
                  name="name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Waters Acquity UPLC H-Class (Empower 3 Workstation)"
                />
              </Field>
            </div>

            {/* Radio buttons for < 6 options per modern-web-guidance (forms) */}
            <div className="grid grid-cols-1 gap-4 rounded-lg border bg-muted/40 p-3.5 sm:grid-cols-2">
              <FieldSet className="gap-2">
                <FieldLegend variant="label">
                  GMP Regulatory Status *
                </FieldLegend>
                <div className="flex flex-wrap gap-3">
                  <FieldLabel className="cursor-pointer text-xs font-semibold">
                    <input
                      type="radio"
                      name="is_gmp_radio"
                      checked={isGmp === true}
                      onChange={() => setIsGmp(true)}
                      className="accent-primary"
                    />
                    GMP Regulated (GLP/GMP/GCP)
                  </FieldLabel>
                  <FieldLabel className="cursor-pointer text-xs font-medium text-muted-foreground">
                    <input
                      type="radio"
                      name="is_gmp_radio"
                      checked={isGmp === false}
                      onChange={() => setIsGmp(false)}
                      className="accent-primary"
                    />
                    Non-GMP (R&amp;D / Discovery)
                  </FieldLabel>
                </div>
              </FieldSet>

              <FieldSet className="gap-2">
                <FieldLegend variant="label">
                  Asset Criticality Tier *
                </FieldLegend>
                <div className="flex flex-wrap gap-3">
                  {(["CRITICAL", "MAJOR", "MINOR"] as const).map((tier) => (
                    <FieldLabel
                      key={tier}
                      className="cursor-pointer text-xs font-semibold"
                    >
                      <input
                        type="radio"
                        name="criticality_radio"
                        value={tier}
                        checked={criticality === tier}
                        onChange={() => setCriticality(tier)}
                        className="accent-primary"
                      />
                      {tier}
                    </FieldLabel>
                  ))}
                </div>
              </FieldSet>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field>
                <FieldLabel htmlFor={`${formId}-cat`}>
                  Equipment Category *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-cat`}
                  name="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full"
                >
                  {EQUIPMENT_CATEGORIES.map((c) => (
                    <NativeSelectOption key={c} value={c}>
                      {c}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-vendor`}>
                  Manufacturer / Vendor *
                </FieldLabel>
                <Input
                  id={`${formId}-vendor`}
                  name="vendor"
                  type="text"
                  required
                  value={vendor}
                  onChange={(e) => setVendor(e.target.value)}
                  placeholder="Waters, Thermo, Illumina..."
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-model`}>Model *</FieldLabel>
                <Input
                  id={`${formId}-model`}
                  name="model"
                  type="text"
                  required
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field>
                <FieldLabel htmlFor={`${formId}-sn`}>
                  Serial Number *
                </FieldLabel>
                <Input
                  id={`${formId}-sn`}
                  name="serial_number"
                  type="text"
                  required
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={serialNumber}
                  onChange={(e) => setSerialNumber(e.target.value)}
                  className="font-mono"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-loc`}>
                  Lab Location / Room *
                </FieldLabel>
                <Input
                  id={`${formId}-loc`}
                  name="location"
                  type="text"
                  required
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-ip`}>
                  Hostname or IP Address *
                </FieldLabel>
                <Input
                  id={`${formId}-ip`}
                  name="hostname_or_ip"
                  type="text"
                  required
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  value={hostnameOrIp}
                  onChange={(e) => setHostnameOrIp(e.target.value)}
                  className="font-mono"
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={`${formId}-os`}>
                  Operating System / Backup Mechanism *
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-os`}
                  name="os_type"
                  value={osType}
                  onChange={(e) => setOsType(e.target.value)}
                  className="w-full"
                >
                  {OS_TYPES.map((o) => (
                    <NativeSelectOption key={o.value} value={o.value}>
                      {o.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-sop`}>
                  Governing Backup &amp; Restore SOP
                </FieldLabel>
                <NativeSelect
                  id={`${formId}-sop`}
                  name="sop_id"
                  value={sopId}
                  onChange={(e) =>
                    setSopId(e.target.value ? Number(e.target.value) : "")
                  }
                  className="w-full"
                >
                  <NativeSelectOption value="">
                    -- None / Select SOP --
                  </NativeSelectOption>
                  {sops.map((s) => (
                    <NativeSelectOption key={s.id} value={s.id}>
                      {s.sop_code} (v{s.version}) - {s.title}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={`${formId}-sysowner`}>
                  System Owner *
                </FieldLabel>
                <Input
                  id={`${formId}-sysowner`}
                  name="system_owner"
                  type="text"
                  required
                  value={systemOwner}
                  onChange={(e) => setSystemOwner(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor={`${formId}-qaowner`}>
                  QA Compliance Owner *
                </FieldLabel>
                <Input
                  id={`${formId}-qaowner`}
                  name="qa_owner"
                  type="text"
                  required
                  value={qaOwner}
                  onChange={(e) => setQaOwner(e.target.value)}
                />
              </Field>
            </div>
          </FieldGroup>

          {(isGmp ||
            criticality === "CRITICAL" ||
            (editingAsset &&
              (editingAsset.is_gmp ||
                editingAsset.criticality === "CRITICAL"))) && (
            <ESignatureFields value={esig} onChange={setEsig} />
          )}

          <Separator />

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">
              {editingAsset
                ? "Sign & Save Asset Changes"
                : "Register Equipment"}
            </Button>
          </div>
        </form>
      </ModalDialog>

      {/* Dynamic Per-Asset Restic Setup Script Generator Modal */}
      <ModalDialog
        isOpen={Boolean(bundleModalAsset)}
        onClose={() => setBundleModalAsset(null)}
        title={
          bundleModalAsset
            ? `Restic Deployment Bundle: ${bundleModalAsset.asset_tag} (${bundleModalAsset.asset_name})`
            : "Restic Bundle"
        }
        maxWidthClass="max-w-4xl"
      >
        {bundleModalAsset && (
          <div className="flex flex-col gap-4">
            <Card size="sm" className="bg-muted/40">
              <CardContent className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <div>
                  <strong className="text-foreground">Agent Token:</strong>{" "}
                  <Badge variant="outline">
                    {bundleModalAsset.agent_token}
                  </Badge>
                </div>
                <div>
                  <strong className="text-foreground">Active Schedule:</strong>{" "}
                  <code className="font-mono text-foreground">
                    {bundleModalAsset.schedule_cron}
                  </code>{" "}
                  &bull;{" "}
                  <strong className="text-foreground">Target Repo:</strong>{" "}
                  <code className="font-mono text-foreground">
                    {bundleModalAsset.repository_uri}
                  </code>
                </div>
              </CardContent>
            </Card>

            <div className="flex flex-wrap gap-2">
              <Button
                variant={bundleTab === "resticprofile" ? "default" : "outline"}
                size="sm"
                onClick={() => setBundleTab("resticprofile")}
              >
                resticprofile (profiles.yaml)
              </Button>
              <Button
                variant={bundleTab === "windows" ? "default" : "outline"}
                size="sm"
                onClick={() => setBundleTab("windows")}
              >
                Windows PowerShell + VSS Script
              </Button>
              <Button
                variant={bundleTab === "unix" ? "default" : "outline"}
                size="sm"
                onClick={() => setBundleTab("unix")}
              >
                macOS / Linux Bash Agent
              </Button>
              <Button
                variant={bundleTab === "agentless" ? "default" : "outline"}
                size="sm"
                onClick={() => setBundleTab("agentless")}
              >
                Agentless Equipment (SMB / SFTP Gateway)
              </Button>
            </div>

            <Separator />

            <figure className="flex flex-col gap-1.5">
              <figcaption className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <Code2 className="size-4 text-primary" aria-hidden="true" />
                {bundleTab === "resticprofile"
                  ? `Declarative resticprofile configuration (profile: ${bundleModalAsset.resticprofile_name}):`
                  : "Self-updating script (polls central CFR-App API for schedule/frequency edits automatically):"}
              </figcaption>
              <pre
                tabIndex={0}
                className="max-h-96 overflow-x-auto rounded-lg border bg-muted p-4 font-mono text-xs text-foreground"
              >
                <code>
                  {bundleTab === "resticprofile"
                    ? bundleModalAsset.resticprofile_yaml
                    : bundleTab === "windows"
                      ? bundleModalAsset.windows_powershell_script
                      : bundleTab === "unix"
                        ? bundleModalAsset.unix_bash_script
                        : bundleModalAsset.agentless_setup_commands}
                </code>
              </pre>
            </figure>
          </div>
        )}
      </ModalDialog>
    </div>
  )
}
