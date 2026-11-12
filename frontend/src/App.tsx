import React, { useEffect, useId, useState } from "react"
import {
  Activity,
  AlertCircle,
  BookOpen,
  Database,
  FileCheck,
  HardDrive,
  LayoutDashboard,
  LogOut,
  RotateCcw,
  ShieldCheck,
  UserCheck,
} from "lucide-react"
import { apiRequest, getAuthToken, setAuthToken } from "./api/client"
import { AssetsView } from "./pages/AssetsView"
import { AuditTrailView } from "./pages/AuditTrailView"
import { DashboardView } from "./pages/DashboardView"
import { PoliciesView } from "./pages/PoliciesView"
import { SnapshotsRestoreView } from "./pages/SnapshotsRestoreView"
import { SopsGuidesView } from "./pages/SopsGuidesView"
import { StorageView } from "./pages/StorageView"
import { User } from "./types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
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

const DEMO_ACCOUNTS = [
  { username: "admin", label: "Dr. Elena Vance (Admin)" },
  { username: "qa_director", label: "Marcus Chen (QA_Compliance)" },
  { username: "lab_eng", label: "Sarah Jenkins (Lab_Engineer)" },
  {
    username: "fda_auditor",
    label: "Inspector David Miller (Auditor - Read Only)",
  },
]

export const App: React.FC = () => {
  const loginFormId = useId()
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [activeTab, setActiveTab] = useState<string>("dashboard")
  const [loadingAuth, setLoadingAuth] = useState<boolean>(true)

  // Login form state
  const [username, setUsername] = useState("qa_director")
  const [password, setPassword] = useState("gmp-password-123")
  const [loginError, setLoginError] = useState<string | null>(null)

  const performLogin = async (userStr: string, passStr: string) => {
    setLoginError(null)
    try {
      const res = await apiRequest<{ access_token: string; user: User }>(
        "/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ username: userStr, password: passStr }),
        }
      )
      setAuthToken(res.access_token)
      setCurrentUser(res.user)
    } catch (err: any) {
      setLoginError(err.message || "Authentication failed")
    }
  }

  useEffect(() => {
    const initAuth = async () => {
      const existing = getAuthToken()
      if (existing) {
        try {
          const me = await apiRequest<User>("/auth/me")
          setCurrentUser(me)
          setLoadingAuth(false)
          return
        } catch {
          setAuthToken(null)
        }
      }
      // Auto-authenticate default QA_Compliance / Admin evaluation account on first visit
      try {
        await performLogin("qa_director", "gmp-password-123")
      } finally {
        setLoadingAuth(false)
      }
    }
    initAuth()
  }, [])

  if (loadingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md">
          <CardContent className="flex items-center justify-center gap-3 py-8 text-sm text-muted-foreground">
            <Spinner className="size-5 text-primary" />
            <span>
              Initializing CFR-App GxP Asset &amp; Restic Backup Platform...
            </span>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
        <Card className="w-full max-w-md shadow-2xl">
          <CardHeader>
            <div className="mb-1 flex items-center gap-2.5 text-xl font-extrabold text-primary">
              <ShieldCheck className="size-7 text-primary" aria-hidden="true" />
              <span>CFR-App GxP Backup</span>
            </div>
            <CardTitle>
              <h1 className="text-lg font-bold text-foreground">
                Life Science Asset &amp; Restic Management Sign In
              </h1>
            </CardTitle>
            <CardDescription>
              21 CFR Part 11 / EU GMP Annex 11 Authenticated Access Control
            </CardDescription>
          </CardHeader>

          <CardContent className="flex flex-col gap-4">
            {loginError && (
              <Alert variant="destructive">
                <AlertCircle aria-hidden="true" />
                <AlertTitle>Authentication Error</AlertTitle>
                <AlertDescription>{loginError}</AlertDescription>
              </Alert>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault()
                performLogin(username, password)
              }}
              className="flex flex-col gap-4"
            >
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor={`${loginFormId}-user`}>
                    Username
                  </FieldLabel>
                  <Input
                    id={`${loginFormId}-user`}
                    name="username"
                    type="text"
                    required
                    autoComplete="username"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </Field>

                <Field>
                  <FieldLabel htmlFor={`${loginFormId}-pass`}>
                    Password
                  </FieldLabel>
                  <Input
                    id={`${loginFormId}-pass`}
                    name="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </Field>
              </FieldGroup>

              <Button type="submit" size="lg" className="w-full">
                Sign In to Regulated Environment
              </Button>
            </form>
          </CardContent>

          <CardFooter className="flex flex-col items-stretch gap-2">
            <div className="text-xs font-bold text-foreground">
              Quick-Login Evaluation Accounts (Password:{" "}
              <code className="font-mono">gmp-password-123</code>):
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {DEMO_ACCOUNTS.map((acc) => (
                <Button
                  key={acc.username}
                  variant="outline"
                  size="sm"
                  onClick={() => performLogin(acc.username, "gmp-password-123")}
                  className="justify-start font-medium"
                >
                  <code className="font-mono">{acc.username}</code> &mdash;{" "}
                  {acc.label}
                </Button>
              ))}
            </div>
          </CardFooter>
        </Card>
      </main>
    )
  }

  const navItems = [
    { id: "dashboard", label: "Compliance Dashboard", icon: LayoutDashboard },
    { id: "assets", label: "Equipment & Criticality", icon: HardDrive },
    { id: "policies", label: "Backup Policies & Schedules", icon: Activity },
    { id: "storage", label: "Storage Backends (S3/REST)", icon: Database },
    { id: "snapshots", label: "Snapshots & Restore Drills", icon: RotateCcw },
    { id: "guides", label: "Equipment Guides & SOPs", icon: BookOpen },
    { id: "audit", label: "21 CFR Part 11 Audit Trail", icon: FileCheck },
  ]

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b bg-card/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg border bg-primary/10 text-primary">
                <ShieldCheck className="size-6" aria-hidden="true" />
              </div>
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-heading text-base font-extrabold tracking-tight text-foreground">
                    CFR-App
                  </span>
                  <Badge variant="sky">21 CFR Part 11 &bull; Restic GxP</Badge>
                </div>
                <p className="hidden text-[11px] text-muted-foreground sm:block">
                  Open-Source Life Science Asset Criticality, Multi-Backend
                  Restic Backup &amp; SOP Restore Platform
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Field orientation="horizontal" className="w-auto items-center">
                <UserCheck
                  className="size-4 text-primary"
                  aria-hidden="true"
                />
                <FieldLabel htmlFor="role-switcher" className="sr-only">
                  Switch Active RBAC Role
                </FieldLabel>
                <NativeSelect
                  id="role-switcher"
                  name="role_switcher"
                  size="sm"
                  value={currentUser.username}
                  onChange={(e) =>
                    performLogin(e.target.value, "gmp-password-123")
                  }
                >
                  {DEMO_ACCOUNTS.map((acc) => (
                    <NativeSelectOption key={acc.username} value={acc.username}>
                      {acc.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>

              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => {
                  setAuthToken(null)
                  setCurrentUser(null)
                }}
                aria-label="Sign out"
              >
                <LogOut aria-hidden="true" />
              </Button>
            </div>
          </div>

          <Separator />

          <nav
            aria-label="Primary Navigation"
            className="flex gap-1 overflow-x-auto py-1.5"
          >
            {navItems.map((item) => {
              const Icon = item.icon
              const active = activeTab === item.id
              return (
                <Button
                  key={item.id}
                  variant={active ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setActiveTab(item.id)}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon data-icon="inline-start" aria-hidden="true" />
                  {item.label}
                </Button>
              )
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {activeTab === "dashboard" && (
          <DashboardView onNavigate={setActiveTab} />
        )}
        {activeTab === "assets" && <AssetsView currentUser={currentUser} />}
        {activeTab === "policies" && <PoliciesView currentUser={currentUser} />}
        {activeTab === "storage" && <StorageView currentUser={currentUser} />}
        {activeTab === "snapshots" && (
          <SnapshotsRestoreView currentUser={currentUser} />
        )}
        {activeTab === "guides" && <SopsGuidesView />}
        {activeTab === "audit" && <AuditTrailView />}
      </main>

      <footer className="mt-12 border-t bg-card py-4">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 text-xs text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
          <div>
            <strong className="text-foreground">CFR-App v1.0.0</strong> &bull;
            Released under the{" "}
            <strong className="text-foreground">MIT Open Source License</strong>{" "}
            for Life Science Organizations
          </div>
          <div>
            Powered by <strong className="text-foreground">Restic</strong>,{" "}
            <strong className="text-foreground">
              Restic REST Server (--append-only)
            </strong>
            , <strong className="text-foreground">FastAPI</strong> &amp;{" "}
            <strong className="text-foreground">PostgreSQL</strong>
          </div>
        </div>
      </footer>
    </div>
  )
}
export default App
