import React, { useEffect, useState } from "react"
import { BookOpen, CheckCircle2, FileText, Terminal } from "lucide-react"
import { apiRequest } from "../api/client"
import { EquipmentGuide, SOPDocument } from "../types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

export const SopsGuidesView: React.FC = () => {
  const [guides, setGuides] = useState<EquipmentGuide[]>([])
  const [sops, setSops] = useState<SOPDocument[]>([])
  const [selectedGuideSlug, setSelectedGuideSlug] = useState<string>("")

  useEffect(() => {
    Promise.all([
      apiRequest<EquipmentGuide[]>("/sops/guides"),
      apiRequest<SOPDocument[]>("/sops"),
    ]).then(([gList, sList]) => {
      setGuides(gList)
      setSops(sList)
      if (gList.length > 0) setSelectedGuideSlug(gList[0].slug)
    })
  }, [])

  const activeGuide =
    guides.find((g) => g.slug === selectedGuideSlug) || guides[0]

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Equipment Backup Guidelines &amp; Approved QMS SOPs
        </h1>
        <p className="text-sm text-muted-foreground">
          Step-by-step validated guidelines for setting up Restic across Windows
          (with VSS), macOS (launchd + Full Disk Access), Linux/Unix (systemd +
          POSIX capabilities), and closed/agentless legacy lab equipment
          (SMB/CIFS, SFTP Landing Zones, USB-Gadget).
        </p>
      </div>

      {/* Equipment Backup Guidelines Hub */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="flex flex-col gap-2 lg:col-span-4">
          <h2 className="px-1 text-xs font-bold tracking-wider text-muted-foreground uppercase">
            Equipment &amp; Storage Setup Guides
          </h2>
          {guides.map((g) => {
            const active = activeGuide?.slug === g.slug
            return (
              <Button
                key={g.slug}
                variant={active ? "default" : "outline"}
                onClick={() => setSelectedGuideSlug(g.slug)}
                className="h-auto w-full flex-col items-start justify-start gap-1 p-3.5 text-left whitespace-normal"
              >
                <div className="flex items-center gap-2 text-xs font-bold">
                  <Terminal
                    data-icon="inline-start"
                    aria-hidden="true"
                  />
                  <span>{g.title}</span>
                </div>
                <div className="font-mono text-[11px] opacity-80">
                  docs/{g.filename}
                </div>
              </Button>
            )
          })}
        </div>

        <div className="lg:col-span-8">
          {activeGuide && (
            <article>
              <Card>
                <CardHeader className="border-b bg-muted/30">
                  <CardTitle>
                    <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
                      <BookOpen
                        className="size-5 text-primary"
                        aria-hidden="true"
                      />
                      {activeGuide.title}
                    </h2>
                  </CardTitle>
                  <CardAction>
                    <Badge variant="secondary">
                      docs/{activeGuide.filename}
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent>
                  <pre
                    tabIndex={0}
                    className="max-h-[600px] overflow-y-auto rounded-lg border bg-muted/40 p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-foreground"
                  >
                    <code>{activeGuide.content_markdown}</code>
                  </pre>
                </CardContent>
              </Card>
            </article>
          )}
        </div>
      </section>

      {/* Approved QMS Backup & Restore SOPs */}
      <section className="flex flex-col gap-4">
        <h2 className="flex items-center gap-2 font-heading text-lg font-bold text-foreground">
          <FileText className="size-5 text-primary" aria-hidden="true" />
          Approved Backup &amp; Restore Standard Operating Procedures (
          {sops.length})
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {sops.map((s) => (
            <Card key={s.id} className="justify-between">
              <CardHeader>
                <CardDescription className="font-mono text-xs font-bold text-primary">
                  {s.sop_code} (v{s.version})
                </CardDescription>
                <CardTitle>
                  <h3 className="text-base font-bold text-foreground">
                    {s.title}
                  </h3>
                </CardTitle>
                <CardAction>
                  <Badge variant="emerald">
                    <CheckCircle2
                      data-icon="inline-start"
                      aria-hidden="true"
                    />
                    {s.status}
                  </Badge>
                </CardAction>
              </CardHeader>

              <CardContent className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-3 rounded-lg border bg-muted/40 p-2.5 text-xs text-muted-foreground">
                  <span>
                    <strong className="text-foreground">Target RPO:</strong>{" "}
                    &le; {s.target_rpo_hours}h
                  </span>
                  <span>
                    <strong className="text-foreground">Target RTO:</strong>{" "}
                    &le; {s.target_rto_hours}h
                  </span>
                  <span>
                    <strong className="text-foreground">
                      Restore Drill Interval:
                    </strong>{" "}
                    Every {s.drill_interval_days} days
                  </span>
                </div>

                <div className="rounded-lg border bg-muted/20 p-3 text-xs whitespace-pre-wrap text-foreground">
                  {s.content_markdown}
                </div>

                <Separator />

                <div className="flex flex-col gap-1.5">
                  <h4 className="text-xs font-bold text-foreground">
                    Mandatory Restore Verification Checklist Steps:
                  </h4>
                  <ol className="flex list-decimal flex-col gap-1 pl-5 text-xs text-muted-foreground">
                    {s.checklist.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                </div>
              </CardContent>

              {s.approved_by && (
                <CardFooter className="text-[11px] text-muted-foreground">
                  QA Electronic Approval:{" "}
                  <strong className="ml-1 text-foreground">
                    {s.approved_by}
                  </strong>
                </CardFooter>
              )}
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
