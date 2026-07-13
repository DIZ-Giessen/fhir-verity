import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { AlertTriangle, CheckCircle2, Play, XCircle } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type BulkActionResult,
  type BulkDeleteRequest,
  type BulkFixRequest,
  bulkDelete,
  bulkFix,
  fixTemplatesQueryOptions,
  resourceTypesQueryOptions,
  serverResourceConfigQueryOptions,
  serversQueryOptions,
} from "@/api/queries"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Corkscrew,
  Lightbulb,
  NotificationLinesRemove,
} from "@solar-icons/react-perf/category/style/LineDuotone"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export const Route = createFileRoute("/cleanup")({ component: CleanupPage })

const ALL = "all"
type Mode = "delete" | "fix"

function CleanupPage() {
  const [mode, setMode] = useState<Mode>("delete")
  const [serverId, setServerId] = useState("")
  const [resourceType, setResourceType] = useState(ALL)
  const [rule, setRule] = useState(ALL)
  const [severity, setSeverity] = useState(ALL)
  const [reason, setReason] = useState("")

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [matched, setMatched] = useState<number | null>(null)
  const [result, setResult] = useState<BulkActionResult | null>(null)

  const serversQ = useQuery(serversQueryOptions())
  const typesQ = useQuery(resourceTypesQueryOptions())
  const fixTemplatesQ = useQuery(fixTemplatesQueryOptions())

  const cfgEnabled = mode === "delete" && !!serverId && resourceType !== ALL
  const cfgQ = useQuery({
    ...serverResourceConfigQueryOptions(serverId, resourceType),
    enabled: cfgEnabled,
  })

  // reset dependent fields
  useEffect(() => {
    setResourceType(ALL)
    setSeverity(ALL)
    setResult(null)
  }, [mode])
  useEffect(() => {
    setRule(ALL)
  }, [resourceType])

  const fixableTypes = useMemo(
    () =>
      Array.from(
        new Set((fixTemplatesQ.data ?? []).map((t) => t.resource_type))
      ).sort(),
    [fixTemplatesQ.data]
  )
  const fixRules = useMemo(
    () =>
      (fixTemplatesQ.data ?? [])
        .filter((t) => t.resource_type === resourceType)
        .map((t) => t.rule)
        .sort(),
    [fixTemplatesQ.data, resourceType]
  )
  const deleteRules = useMemo(
    () => Object.keys(cfgQ.data?.rules ?? {}).sort(),
    [cfgQ.data]
  )

  const canRun =
    mode === "delete"
      ? !!serverId
      : !!serverId && resourceType !== ALL && rule !== ALL

  function buildBody(dry: boolean): BulkDeleteRequest | BulkFixRequest {
    if (mode === "delete") {
      return {
        server_id: serverId,
        resource_type: resourceType === ALL ? null : resourceType,
        rule: rule === ALL ? null : rule,
        severity: severity === ALL ? null : severity,
        dry_run: dry,
        reason: reason.trim() || null,
      }
    }
    return {
      server_id: serverId,
      resource_type: resourceType,
      rule,
      dry_run: dry,
      reason: reason.trim() || null,
    }
  }

  const previewM = useMutation({
    mutationFn: () =>
      mode === "delete"
        ? bulkDelete(buildBody(true) as BulkDeleteRequest)
        : bulkFix(buildBody(true) as BulkFixRequest),
    onSuccess: (res) => {
      if (!res) return
      setMatched(res.matched)
      if (res.matched === 0) {
        toast.info("No resources match these filters")
        return
      }
      setConfirmOpen(true)
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Preview failed"),
  })

  const executeM = useMutation({
    mutationFn: () =>
      mode === "delete"
        ? bulkDelete(buildBody(false) as BulkDeleteRequest)
        : bulkFix(buildBody(false) as BulkFixRequest),
    onSuccess: (res) => {
      setConfirmOpen(false)
      if (!res) return
      setResult(res)
      toast.success(`${res.succeeded} succeeded, ${res.failed} failed`)
    },
    onError: (e: unknown) => {
      setConfirmOpen(false)
      toast.error(e instanceof Error ? e.message : "Execution failed")
    },
  })

  const serverName =
    serversQ.data?.find((s) => s.id === serverId)?.name ?? serverId

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cleanup</h1>
        <p className="text-sm text-muted-foreground">
          Bulk-delete or bulk-fix invalid resources on a FHIR server. Every run
          previews matches first before anything is executed.
        </p>
      </div>

      <Card className="shadow-none">
        <CardHeader className="gap-4">
          <Tabs
            value={mode}
            onValueChange={(v) => setMode(v as Mode)}
            className="w-full"
          >
            <TabsList className="w-full">
              <TabsTrigger
                value="delete"
                className="gap-1 data-[state=active]:text-orange-500 data-[state=active]:dark:text-orange-500"
              >
                <NotificationLinesRemove className="size-4" />
                Delete Invalid Resources
              </TabsTrigger>
              <TabsTrigger
                value="fix"
                className="gap-1 data-[state=active]:text-orange-500 data-[state=active]:dark:text-orange-500"
              >
                <Corkscrew className="size-4" />
                Fix Invalid Resources
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <CardTitle className="mt-4 text-base">
            {mode === "delete"
              ? "Delete invalid resources matching a filter"
              : "Apply a patch template to a (resource type, rule) combination"}
          </CardTitle>
        </CardHeader>

        <CardContent className="grid gap-4 sm:grid-cols-6">
          <div className="space-y-1.5">
            <Label>Server</Label>
            <Select value={serverId} onValueChange={setServerId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a server" />
              </SelectTrigger>
              <SelectContent className="max-h-80 overflow-auto">
                {(serversQ.data ?? []).map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Resource type</Label>
            <Select value={resourceType} onValueChange={setResourceType}>
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    mode === "fix" ? "Select a type" : "All resource types"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {mode === "delete" && (
                  <SelectItem value={ALL}>All resource types</SelectItem>
                )}
                {(mode === "fix" ? fixableTypes : (typesQ.data ?? [])).map(
                  (t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Rule</Label>
            <Select
              value={rule}
              onValueChange={setRule}
              disabled={resourceType === ALL}
            >
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    resourceType === ALL
                      ? "Pick a resource type first"
                      : mode === "fix"
                        ? "Select a rule"
                        : "All rules"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {mode === "delete" && (
                  <SelectItem value={ALL}>All rules</SelectItem>
                )}
                {(mode === "fix" ? fixRules : deleteRules).map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {mode === "delete" && (
            <div className="space-y-1.5">
              <Label>Severity</Label>
              <Select value={severity} onValueChange={setSeverity}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="All severities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All severities</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="w-full space-y-1.5 sm:col-span-2">
            <Label>Reason (audit log)</Label>
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="This is optional."
            />
          </div>
        </CardContent>

        <CardFooter className="justify-end">
          <Button
            disabled={!canRun || previewM.isPending}
            onClick={() => previewM.mutate()}
            className="gap-1"
          >
            <Play className="h-4 w-4" />
            {previewM.isPending ? "Checking..." : "Preview matches"}
          </Button>
        </CardFooter>
      </Card>

      {result && (
        <Card className="shadow-2xs">
          <CardHeader>
            <CardTitle className="text-base">Result</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Matched: {result.matched}</Badge>
              <Badge
                variant="outline"
                className="border-0 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
              >
                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                Succeeded: {result.succeeded}
              </Badge>
              {result.failed > 0 && (
                <Badge
                  variant="outline"
                  className="border-0 bg-red-500/15 text-red-700 dark:text-red-400"
                >
                  <XCircle className="mr-1 h-3.5 w-3.5" />
                  Failed: {result.failed}
                </Badge>
              )}
              <Badge variant="outline">{result.elapsed_seconds}s</Badge>
            </div>

            {result.errors.length > 0 && (
              <div className="max-h-64 overflow-auto rounded-lg border">
                <ul className="divide-y text-sm">
                  {result.errors.map((err, i) => (
                    <li key={i} className="px-3 py-2">
                      <span className="font-mono text-xs">
                        {err.resource_type}/{err.resource_id}
                      </span>
                      <span className="ml-2 text-muted-foreground">
                        {err.error}
                      </span>
                    </li>
                  ))}
                </ul>
                {result.failed > result.errors.length && (
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    {result.failed - result.errors.length} more errors not shown
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(o) => !o && !executeM.isPending && setConfirmOpen(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              {mode === "delete" ? "Confirm bulk delete" : "Confirm bulk fix"}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>
                  <span className="font-semibold text-foreground">
                    {matched?.toLocaleString()}
                  </span>{" "}
                  resources match on{" "}
                  <span className="font-mono">{serverName}</span>.
                </p>
                <p className="text-xs">
                  {resourceType === ALL ? "All types" : resourceType}
                  {rule !== ALL ? ` / ${rule}` : ""}
                  {mode === "delete" && severity !== ALL
                    ? ` / ${severity}`
                    : ""}
                </p>
                {mode === "delete" && (
                  <p className="text-red-600 dark:text-red-400">
                    This deletes them from the FHIR server and cannot be undone.
                  </p>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={executeM.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={executeM.isPending}
              className={mode === "delete" ? "bg-red-600 hover:bg-red-700" : ""}
              onClick={(e) => {
                e.preventDefault()
                executeM.mutate()
              }}
            >
              {executeM.isPending
                ? "Executing..."
                : mode === "delete"
                  ? "Delete all"
                  : "Fix all"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Alert className="border-0 shadow-none">
        <Lightbulb />
        <AlertTitle>Important Information</AlertTitle>
        <AlertDescription>
          Please review this information before deleting or fixing the
          resources.
          <ul className="list-disc pl-5">
            <li>
              The fix works only on HAPI FHIR servers, as it is based on the
              PATCH method, which is not supported by some Blaze servers.
            </li>
            <li>
              After validation, the request is immediately added to the audit
              logs, regardless of success or failure.
            </li>
            <li>
              A resource cannot be deleted if it is referenced by another
              resource (referential integrity).
            </li>
            <li>The fix only works for Patient and Observation resources.</li>
          </ul>
          <Button
            variant="link"
            size="sm"
            className="text-info h-auto p-0 underline"
          >
            Read more here
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  )
}
