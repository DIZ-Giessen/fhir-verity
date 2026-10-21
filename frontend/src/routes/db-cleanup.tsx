import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { AlertTriangle, CalendarIcon, Play } from "lucide-react"
import { useState } from "react"
import { format } from "date-fns"
import { de } from "date-fns/locale"
import { toast } from "sonner"

import { CheckCircleIcon, LightbulbIcon } from "@solar-icons/react/line-duotone"
import type { DbPurgeRequest, DbPurgeResult } from "@/api/queries"
import {
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { TextDots } from "@/components/text-dots"
import {
  AnimatedLoadingText,
  LoadingCheckMessage,
  PurgeText,
  useLoadingText,
} from "@/lib/interface/loading"

export const Route = createFileRoute("/db-cleanup")({
  component: DbCleanupPage,
})

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
          {value ? (
            format(value, "PPP", { locale: de })
          ) : (
            <span>{placeholder}</span>
          )}
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
  const [serverId, setServerId] = useState("")
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
    resourceType === ALL &&
    !rule.trim() &&
    severity === ALL &&
    !lastSeenBefore &&
    !lastSeenAfter

  function buildBody(dry: boolean): DbPurgeRequest {
    return {
      server_id: serverId,
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
    serversQ.data?.find((s) => s.id === serverId)?.name ?? serverId

  const loadingText = useLoadingText(LoadingCheckMessage)
  const purgeText = useLoadingText(PurgeText)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Database Cleanup
        </h1>
        <p className="text-sm text-muted-foreground">
          Remove entries from Verity&apos;s <code>invalid_resources</code> table
          only. The FHIR server is never contacted.
        </p>
      </div>
      {result && (
        <>
          <Alert className="border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:border-emerald-900/20 dark:bg-emerald-900/10 dark:text-emerald-400">
            <CheckCircleIcon />
            <AlertTitle className="font-semibold">
              Database purge successful
            </AlertTitle>
            <AlertDescription className="text-sm">
              {result.deleted} entries purged from the database.
            </AlertDescription>
          </Alert>
        </>
      )}
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
          {isUnscoped && serverId && (
            <p className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              No type/rule/severity/date filters set — this will match every
              invalid_resources entry on this server.
            </p>
          )}
          <div className="flex justify-end">
            <Button
              disabled={!serverId || previewM.isPending}
              onClick={() => previewM.mutate()}
              className="gap-1"
            >
              {!previewM.isPending && <Play className="h-4 w-4" />}
              {previewM.isPending ? (
                <TextDots>
                  <AnimatedLoadingText text={loadingText} className="mr-1" />
                </TextDots>
              ) : (
                "Preview matches"
              )}
            </Button>
          </div>
        </CardFooter>
      </Card>

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
                  This removes them from Verity&apos;s database only and cannot
                  be undone. The resources on the FHIR server are not touched.
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
              {executeM.isPending ? (
                <TextDots>
                  <AnimatedLoadingText text={purgeText} className="mr-1" />
                </TextDots>
              ) : (
                "Purge from database"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Alert className="border-0 shadow-none">
        <LightbulbIcon className="size-6 text-blue-500!" />
        <AlertTitle>Important Information</AlertTitle>
        <AlertDescription>
          <ul className="list-disc pl-5">
            <li>
              This only deletes rows from Verity&apos;s own database. It never
              sends a request to the FHIR server — resources are neither
              modified nor deleted there. Use the{" "}
              <span className="font-medium text-foreground">Cleanup</span> page
              instead if you want to act on the FHIR server itself.
            </li>
            <li>
              Every completed validation run already removes entries that are no
              longer confirmed invalid — this page is for one-off cleanup of
              older backlog, or narrowing what Verity keeps tracking.
            </li>
          </ul>
        </AlertDescription>
      </Alert>
    </div>
  )
}
