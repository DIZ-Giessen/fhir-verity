import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { AlertTriangle, CalendarIcon, CheckCircle2, Play } from "lucide-react"
import { useState } from "react"
import { format } from "date-fns"
import { de } from "date-fns/locale"
import { toast } from "sonner"

import {
  type DbPurgeRequest,
  type DbPurgeResult,
  dbPurge,
  resourceTypesQueryOptions,
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Lightbulb } from "@solar-icons/react-perf/category/style/LineDuotone"

export const Route = createFileRoute("/db-cleanup")({ component: DbCleanupPage })

const ALL = "all"

function DateField({
  value,
  onChange,
  placeholder,
}: {
  value: Date | undefined
  onChange: (d: Date | undefined) => void
  placeholder: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          data-empty={!value}
          className="h-9 w-full justify-between text-left text-sm font-normal data-[empty=true]:text-muted-foreground"
        >
          {value ? format(value, "PPP", { locale: de }) : <span>{placeholder}</span>}
          <CalendarIcon className="h-3.5 w-3.5 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value}
          captionLayout="dropdown"
          onSelect={(d) => {
            onChange(d)
            setOpen(false)
          }}
          defaultMonth={value}
        />
      </PopoverContent>
    </Popover>
  )
}

function DbCleanupPage() {
  const [serverId, setServerId] = useState(ALL)
  const [resourceType, setResourceType] = useState(ALL)
  const [rule, setRule] = useState("")
  const [severity, setSeverity] = useState(ALL)
  const [lastSeenBefore, setLastSeenBefore] = useState<Date | undefined>()
  const [lastSeenAfter, setLastSeenAfter] = useState<Date | undefined>()
  const [reason, setReason] = useState("")

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [matched, setMatched] = useState<number | null>(null)
  const [result, setResult] = useState<DbPurgeResult | null>(null)

  const serversQ = useQuery(serversQueryOptions())
  const typesQ = useQuery(resourceTypesQueryOptions())

  const isUnscoped =
    serverId === ALL &&
    resourceType === ALL &&
    !rule.trim() &&
    severity === ALL &&
    !lastSeenBefore &&
    !lastSeenAfter

  function buildBody(dry: boolean): DbPurgeRequest {
    return {
      server_id: serverId === ALL ? null : serverId,
      resource_type: resourceType === ALL ? null : resourceType,
      rule: rule.trim() || null,
      severity: severity === ALL ? null : severity,
      last_seen_before: lastSeenBefore ? lastSeenBefore.toISOString() : null,
      last_seen_after: lastSeenAfter ? lastSeenAfter.toISOString() : null,
      dry_run: dry,
      reason: reason.trim() || null,
    }
  }

  const previewM = useMutation({
    mutationFn: () => dbPurge(buildBody(true)),
    onSuccess: (res) => {
      if (!res) return
      setMatched(res.matched)
      if (res.matched === 0) {
        toast.info("No invalid_resources entries match these filters")
        return
      }
      setConfirmOpen(true)
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "Preview failed"),
  })

  const executeM = useMutation({
    mutationFn: () => dbPurge(buildBody(false)),
    onSuccess: (res) => {
      setConfirmOpen(false)
      if (!res) return
      setResult(res)
      toast.success(`${res.deleted} entries purged from the database`)
    },
    onError: (e: unknown) => {
      setConfirmOpen(false)
      toast.error(e instanceof Error ? e.message : "Purge failed")
    },
  })

  const serverName =
    serverId === ALL
      ? "all servers"
      : (serversQ.data?.find((s) => s.id === serverId)?.name ?? serverId)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Database Cleanup
        </h1>
        <p className="text-sm text-muted-foreground">
          Remove entries from Verity&apos;s <code>invalid_resources</code>{" "}
          table only. The FHIR server is never contacted — nothing is
          deleted or changed there.
        </p>
      </div>

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle className="text-base">
            Purge invalid_resources entries matching a filter
          </CardTitle>
        </CardHeader>

        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Server</Label>
            <Select value={serverId} onValueChange={setServerId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="All servers" />
              </SelectTrigger>
              <SelectContent className="max-h-80 overflow-auto">
                <SelectItem value={ALL}>All servers</SelectItem>
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
                <SelectValue placeholder="All resource types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All resource types</SelectItem>
                {(typesQ.data ?? []).map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

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

          <div className="space-y-1.5">
            <Label>Rule (optional)</Label>
            <Input
              value={rule}
              onChange={(e) => setRule(e.target.value)}
              placeholder="e.g. status_required"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Not seen invalid since before</Label>
            <DateField
              value={lastSeenBefore}
              onChange={setLastSeenBefore}
              placeholder="No lower bound"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Last seen invalid after</Label>
            <DateField
              value={lastSeenAfter}
              onChange={setLastSeenAfter}
              placeholder="No upper bound"
            />
          </div>

          <div className="space-y-1.5 sm:col-span-3">
            <Label>Reason (audit log)</Label>
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="This is optional."
            />
          </div>
        </CardContent>

        <CardFooter className="flex-col items-stretch gap-2">
          {isUnscoped && (
            <p className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              No filters set — this will match every invalid_resources entry
              on every server.
            </p>
          )}
          <div className="flex justify-end">
            <Button
              disabled={previewM.isPending}
              onClick={() => previewM.mutate()}
              className="gap-1"
            >
              <Play className="h-4 w-4" />
              {previewM.isPending ? "Checking..." : "Preview matches"}
            </Button>
          </div>
        </CardFooter>
      </Card>

      {result && (
        <Card className="shadow-2xs">
          <CardHeader>
            <CardTitle className="text-base">Result</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Matched: {result.matched}</Badge>
              <Badge
                variant="outline"
                className="border-0 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
              >
                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                Deleted: {result.deleted}
              </Badge>
              <Badge variant="outline">{result.elapsed_seconds}s</Badge>
            </div>
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
              Confirm database purge
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>
                  <span className="font-semibold text-foreground">
                    {matched?.toLocaleString()}
                  </span>{" "}
                  entries match on{" "}
                  <span className="font-mono">{serverName}</span>.
                </p>
                <p className="text-xs">
                  {resourceType === ALL ? "All types" : resourceType}
                  {rule.trim() ? ` / ${rule.trim()}` : ""}
                  {severity !== ALL ? ` / ${severity}` : ""}
                  {lastSeenBefore
                    ? ` / before ${format(lastSeenBefore, "PPP", { locale: de })}`
                    : ""}
                  {lastSeenAfter
                    ? ` / after ${format(lastSeenAfter, "PPP", { locale: de })}`
                    : ""}
                </p>
                <p className="text-red-600 dark:text-red-400">
                  This removes them from Verity&apos;s database only and
                  cannot be undone. The resources on the FHIR server are not
                  touched.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={executeM.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={executeM.isPending}
              className="bg-red-600 hover:bg-red-700"
              onClick={(e) => {
                e.preventDefault()
                executeM.mutate()
              }}
            >
              {executeM.isPending ? "Purging..." : "Purge from database"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Alert className="border-0 shadow-none">
        <Lightbulb />
        <AlertTitle>Important Information</AlertTitle>
        <AlertDescription>
          <ul className="list-disc pl-5">
            <li>
              This only deletes rows from Verity&apos;s own database. It
              never sends a request to the FHIR server — resources are
              neither modified nor deleted there. Use the{" "}
              <span className="font-medium text-foreground">Cleanup</span>{" "}
              page instead if you want to act on the FHIR server itself.
            </li>
            <li>
              Every completed validation run already removes entries that
              are no longer confirmed invalid — this page is for one-off
              cleanup of older backlog, or narrowing what Verity keeps
              tracking.
            </li>
            <li>
              Every purge is written to the{" "}
              <span className="font-medium text-foreground">Audit</span> log,
              one entry per removed resource, regardless of filters used.
            </li>
          </ul>
        </AlertDescription>
      </Alert>
    </div>
  )
}
