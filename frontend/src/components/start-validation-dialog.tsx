import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ExternalLink, Filter, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { DangerTriangleIcon } from "@solar-icons/react/line-duotone"
import { Alert, AlertDescription, AlertTitle } from "./ui/alert"
import {
  resourceTypesQueryOptions,
  serverResourceConfigQueryOptions,
  serverResourceCountsQueryOptions,
  serversQueryOptions,
  startValidation,
} from "@/api/queries"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ServerPicker } from "@/components/server-picker"
import { Skeleton } from "@/components/ui/skeleton"
import { apiErrorMessage } from "@/lib/api-client"
import { filterEntries, hasActiveFilters } from "@/lib/filter-format"

const DEFAULT_UNCHECKED_TYPES = new Set([
  "Condition",
  "Observation",
  "Medication",
  "MedicationAdministration",
  "MedicationStatement",
  "Procedure",
  "DiagnosticReport",
  "MedicationRequest",
  "Patient",
  "Encounter",
])

/** Above this many resources a type is called out as a long-running run. */
const LARGE_TYPE_THRESHOLD = 2_000_000

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
})

interface StartValidationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Fixed-server mode (e.g. server detail). Omit for the picker mode. */
  serverId?: string
  serverName?: string
}

export function StartValidationDialog({
  open,
  onOpenChange,
  serverId,
  serverName,
}: StartValidationDialogProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const typesQ = useQuery(resourceTypesQueryOptions())
  const serversQ = useQuery({ ...serversQueryOptions(), enabled: !serverId })

  const allTypes = typesQ.data ?? []
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [pickedServer, setPickedServer] = useState<string>()
  const seededRef = useRef(false)

  // default-select all types except DEFAULT_UNCHECKED_TYPES when the dialog opens
  useEffect(() => {
    if (open && allTypes.length && !seededRef.current) {
      setSelected(
        new Set(allTypes.filter((rt) => !DEFAULT_UNCHECKED_TYPES.has(rt)))
      )
      seededRef.current = true
    }
    if (!open) {
      seededRef.current = false
      setPickedServer(undefined)
    }
  }, [open, allTypes])

  const effectiveServerId = serverId ?? pickedServer
  const effectiveName =
    serverName ?? serversQ.data?.find((s) => s.id === pickedServer)?.name

  // Look up the active per-resource-type filter (lastUpdate/profile/tag) for
  // the target server, so a checked resource that only sees a slice of the
  // data can be called out before the run starts.
  const configQs = useQueries({
    queries: allTypes.map((rt) => ({
      ...serverResourceConfigQueryOptions(effectiveServerId ?? "", rt),
      enabled: Boolean(effectiveServerId) && allTypes.length > 0,
    })),
  })
  const countsQ = useQuery({
    ...serverResourceCountsQueryOptions(effectiveServerId ?? ""),
    enabled: open && Boolean(effectiveServerId),
  })
  const counts = new Map(
    (countsQ.data ?? [])
      .filter((c) => c.ok)
      .map((c) => [c.resource_type, c.total])
  )
  const largeSelectedTypes = allTypes
    .filter((rt) => selected.has(rt))
    .map((rt) => ({ resourceType: rt, total: counts.get(rt) ?? 0 }))
    .filter((x) => x.total > LARGE_TYPE_THRESHOLD)

  const filteredSelectedTypes = allTypes
    .map((rt, i) => ({ resourceType: rt, filters: configQs[i]?.data?.filters }))
    .filter(
      (x): x is { resourceType: string; filters: Record<string, unknown> } =>
        selected.has(x.resourceType) && hasActiveFilters(x.filters)
    )

  const mutation = useMutation({
    mutationFn: (vars: { server_id: string; resource_types: Array<string> }) =>
      startValidation(vars),
    onSuccess: (run) => {
      if (!run) return
      queryClient.invalidateQueries({ queryKey: ["validation", "runs"] })
      onOpenChange(false)
      const runId = run.id
      const name = effectiveName
      toast.custom((t) => (
        <div className="flex w-100 flex-col gap-2 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-lg">
          <div className="flex items-center gap-2">
            <span className="flex size-2 animate-pulse rounded-full bg-emerald-500" />
            <p className="animate-pulse text-sm font-medium">
              Validation started
            </p>
          </div>
          <div className="space-y-1 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Server</span>
              <span className="font-medium text-foreground">{name ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Status</span>
              <span className="font-medium text-foreground">{run.status}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Run</span>
              <span className="font-mono font-medium text-foreground">
                {runId.slice(0, 8)}
              </span>
            </div>
          </div>
          <div className="mt-1 flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="flex-1"
              onClick={() => {
                navigate({
                  to: "/runs/$runId/invalid-resources",
                  params: { runId },
                })
                toast.dismiss(t)
              }}
            >
              Invalid resources
            </Button>
            <Button
              size="sm"
              className="flex-1 gap-1"
              onClick={() => {
                navigate({ to: "/runs/$runId/live", params: { runId } })
                toast.dismiss(t)
              }}
            >
              <ExternalLink className="size-3" />
              Live view
            </Button>
          </div>
        </div>
      ))
    },
    onError: (err) => {
      toast.error("Failed to start validation", {
        description: apiErrorMessage(err),
      })
    },
  })

  const toggle = (rt: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(rt)) next.delete(rt)
      else next.add(rt)
      return next
    })

  function handleStart() {
    if (!effectiveServerId || selected.size === 0) return
    const all = allTypes.length > 0 && selected.size === allTypes.length
    mutation.mutate({
      server_id: effectiveServerId,
      resource_types: all ? ["All"] : Array.from(selected),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl!">
        <DialogHeader>
          <DialogTitle>Start validation</DialogTitle>
          <DialogDescription>
            {serverName ? (
              <>
                Run validation against{" "}
                <span className="font-medium">{serverName}</span>.
              </>
            ) : (
              "Select a server and the resource types to validate."
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="-mx-4 no-scrollbar grid max-h-[50vh] gap-4 overflow-y-auto px-4">
          {!serverId && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">
                Server
              </p>
              <ServerPicker
                servers={serversQ.data ?? []}
                value={pickedServer}
                onChange={setPickedServer}
              />
            </div>
          )}

          {largeSelectedTypes.length > 0 && (
            <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-50">
              <DangerTriangleIcon className="size-5" />
              <AlertTitle>Large resource types selected</AlertTitle>
              <AlertDescription>
                <p>
                  {largeSelectedTypes.length === 1
                    ? "This type has"
                    : "These types have"}{" "}
                  more than {compactNumber.format(LARGE_TYPE_THRESHOLD)}{" "}
                  resources on this server, so the run can take{" "}
                  <span className="font-medium text-foreground">
                    significantly longer
                  </span>
                  .
                  {largeSelectedTypes.length > 1 &&
                    " We recommend validating them one at a time."}
                </p>
                <ul className="mt-1 space-y-0.5">
                  {largeSelectedTypes.map(({ resourceType, total }) => (
                    <li
                      key={resourceType}
                      className="list-inside list-disc text-xs"
                    >
                      <span className="text-sm font-medium text-foreground">
                        {resourceType}
                      </span>
                      : {total.toLocaleString()}
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">
              Resource types
            </p>
            {typesQ.isPending ? (
              <div className="grid grid-cols-2 gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-9 w-full" />
                ))}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-1">
                  {allTypes.map((rt) => (
                    <label
                      key={rt}
                      className="flex cursor-pointer items-center gap-2 rounded-lg p-2 text-sm hover:bg-muted/50"
                    >
                      <Checkbox
                        checked={selected.has(rt)}
                        onCheckedChange={() => toggle(rt)}
                      />
                      <span>{rt}</span>
                      {counts.has(rt) && (
                        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                          {compactNumber.format(counts.get(rt) ?? 0)}
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>

          {filteredSelectedTypes.length > 0 && (
            <Alert className="border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-50">
              <Filter className="size-5" />
              <AlertTitle>Filter active</AlertTitle>
              <AlertDescription>
                <p>
                  This run will only cover the resources matching the filter
                  configured for this server. It will not cover the full
                  dataset:
                </p>
                <ul className="mt-1 space-y-0.5">
                  {filteredSelectedTypes.map(({ resourceType, filters }) => (
                    <li
                      key={resourceType}
                      className="list-inside list-disc text-xs"
                    >
                      <span className="text-sm font-medium text-foreground">
                        {resourceType}
                      </span>
                      :{" "}
                      {filterEntries(filters)
                        .map((e) => `${e.label.toLowerCase()} ${e.value}`)
                        .join(", ")}
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
        </div>
        <DialogFooter className="">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleStart}
            disabled={
              !effectiveServerId ||
              selected.size === 0 ||
              mutation.isPending ||
              typesQ.isPending
            }
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {mutation.isPending ? "Starting…" : "Start"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
