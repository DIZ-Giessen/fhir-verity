import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  XIcon,
} from "lucide-react"
import { Fragment, useEffect, useMemo, useState } from "react"

import {
  LinkRoundIcon,
  PenNewSquareIcon,
  RestartIcon,
  TrashBinMinimalisticIcon,
} from "@solar-icons/react/line-duotone"
import { toast } from "sonner"
import type { InvalidResourcesParams } from "@/lib/interface"
import type { InvalidResourceRead } from "@/api/queries"
import {
  autoFixResource,
  deleteResource,
  fixTemplatesQueryOptions,
  invalidResourcesQueryOptions,
  resourceTypesQueryOptions,
  runQueryOptions,
  runSummaryQueryOptions,
} from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { SortableTableHead, nextSort } from "@/components/sortable-table-head"
import { dateFormatter } from "@/lib/functions/runs"
import { SEVERITY_ORDER, SEVERITY_STYLES } from "@/lib/severity"
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
import { Separator } from "@/components/ui/separator"

export const Route = createFileRoute("/runs/$runId_/invalid-resources")({
  component: InvalidResourcesPage,
})

const PAGE_SIZE = 25
const ALL = "all"

function InvalidResourcesPage() {
  const { runId } = Route.useParams()

  const [page, setPage] = useState(0)
  const [resourceTypes, setResourceTypes] = useState<Set<string>>(new Set())
  const [rule, setRule] = useState(ALL)
  const [severity, setSeverity] = useState(ALL)
  const [onlyCurrent, setOnlyCurrent] = useState(true)
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" }>({
    key: "detected",
    dir: "desc",
  })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // any filter/sort change -> back to first page
  useEffect(() => {
    setPage(0)
  }, [resourceTypes, rule, severity, onlyCurrent, sort])

  const params: InvalidResourcesParams = {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    resource_types:
      resourceTypes.size > 0 ? Array.from(resourceTypes) : undefined,
    rule: rule === ALL ? undefined : rule,
    severity: severity === ALL ? undefined : severity,
    only_current_run: onlyCurrent,
    sort_by: sort.key,
    sort_dir: sort.dir,
  }

  const listQ = useQuery(invalidResourcesQueryOptions(runId, params))
  const typesQ = useQuery(resourceTypesQueryOptions())
  const summaryQ = useQuery(runSummaryQueryOptions(runId))

  const runQ = useQuery(runQueryOptions(runId))
  const fixTemplatesQ = useQuery(fixTemplatesQueryOptions())
  const serverId = runQ.data?.server_id

  const fixableSet = useMemo(
    () =>
      new Set(
        (fixTemplatesQ.data ?? []).map((t) => `${t.resource_type}:${t.rule}`)
      ),
    [fixTemplatesQ.data]
  )

  // Rules classified by the resource type they occur on — a flat, pooled
  // rule list mixes up same-named rules from unrelated resource types (e.g.
  // "status_required" exists on Encounter, Observation, DiagnosticReport...).
  const rulesByResourceType = useMemo(() => {
    const map = new Map<string, Array<string>>()
    for (const rt of summaryQ.data?.by_resource_type ?? []) {
      const rules = Array.from(new Set(rt.by_rule.map((r) => r.rule))).sort()
      if (rules.length > 0) map.set(rt.resource_type, rules)
    }
    return map
  }, [summaryQ.data])

  // The resource types the Rule dropdown should draw from: the selection if
  // one is made, otherwise every resource type with recorded rules.
  const ruleScopeTypes = useMemo(() => {
    const types =
      resourceTypes.size > 0
        ? Array.from(resourceTypes).filter((rt) => rulesByResourceType.has(rt))
        : Array.from(rulesByResourceType.keys())
    return types.sort()
  }, [resourceTypes, rulesByResourceType])

  // If the resource type selection changes and the picked rule no longer
  // applies to the new scope, fall back to "All rules" instead of silently
  // keeping a filter that can never match.
  useEffect(() => {
    if (rule === ALL) return
    const stillValid = ruleScopeTypes.some((rt) =>
      rulesByResourceType.get(rt)?.includes(rule)
    )
    if (!stillValid) setRule(ALL)
  }, [rule, ruleScopeTypes, rulesByResourceType])

  const items = listQ.data?.items ?? []
  const total = listQ.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters = resourceTypes.size > 0 || rule !== ALL || severity !== ALL

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-6">
      <Link
        to="/runs/$runId"
        params={{ runId }}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="mr-1 h-4 w-4" />
        Back to run
      </Link>

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Invalid resources
        </h1>
        <p className="font-mono text-xs text-muted-foreground">
          for run with ID {runId}
        </p>
      </div>

      <Card className="shadow-2xs">
        <CardHeader className="gap-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Worklist</CardTitle>
            <p className="text-xs text-muted-foreground">
              {total.toLocaleString()} total
            </p>
          </div>
          <div className="grid items-center gap-2 sm:grid-cols-5">
            <ResourceTypeMultiSelect
              options={typesQ.data ?? []}
              selected={resourceTypes}
              onChange={setResourceTypes}
            />

            <Select value={rule} onValueChange={setRule}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Rule" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All rules</SelectItem>
                {ruleScopeTypes.length === 1 ? (
                  (rulesByResourceType.get(ruleScopeTypes[0]) ?? []).map(
                    (r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    )
                  )
                ) : (
                  <>
                    {ruleScopeTypes.map((rt) => (
                      <SelectGroup key={rt}>
                        <SelectLabel>{rt}</SelectLabel>
                        {(rulesByResourceType.get(rt) ?? []).map((r) => (
                          <SelectItem key={`${rt}:${r}`} value={r}>
                            {r}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    ))}
                  </>
                )}
              </SelectContent>
            </Select>

            <Select value={severity} onValueChange={setSeverity}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All severities</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>

            <Tooltip>
              <TooltipTrigger asChild>
                <label className="flex w-full items-center gap-2 text-sm">
                  <Switch
                    checked={onlyCurrent}
                    onCheckedChange={setOnlyCurrent}
                  />
                  Only this run
                </label>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-64">
                {onlyCurrent
                  ? "Showing only resources still invalid as of this run. Turn off to see every resource ever flagged invalid for this server, even if a later run stopped reconfirming it."
                  : "Showing every resource ever flagged invalid for this server, regardless of run. Turn on to see only what this specific run confirmed as still invalid."}
              </TooltipContent>
            </Tooltip>

            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setResourceTypes(new Set())
                  setRule(ALL)
                  setSeverity(ALL)
                }}
              >
                Reset
                <RestartIcon className="ml-1 h-4 w-4" />
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent>
          {listQ.isPending ? (
            <div className="space-y-2">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No invalid resources match the current filters.
            </p>
          ) : (
            <div
              className={
                listQ.isPlaceholderData ? "opacity-60 transition-opacity" : ""
              }
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <SortableTableHead
                      label="Resource type"
                      sortKey="resource_type"
                      activeKey={sort.key}
                      dir={sort.dir}
                      onSort={(key) =>
                        setSort((prev) => nextSort(prev, key, "asc"))
                      }
                    />
                    <SortableTableHead
                      label="Resource ID"
                      sortKey="resource_id"
                      activeKey={sort.key}
                      dir={sort.dir}
                      onSort={(key) =>
                        setSort((prev) => nextSort(prev, key, "asc"))
                      }
                    />
                    <SortableTableHead
                      label="Severity"
                      sortKey="severity"
                      activeKey={sort.key}
                      dir={sort.dir}
                      onSort={(key) =>
                        setSort((prev) => nextSort(prev, key, "asc"))
                      }
                    />
                    <SortableTableHead
                      label="Issues"
                      sortKey="issues"
                      activeKey={sort.key}
                      dir={sort.dir}
                      onSort={(key) =>
                        setSort((prev) => nextSort(prev, key, "desc"))
                      }
                      className="text-right"
                      align="right"
                    />
                    <SortableTableHead
                      label="Detected"
                      sortKey="detected"
                      activeKey={sort.key}
                      dir={sort.dir}
                      onSort={(key) =>
                        setSort((prev) => nextSort(prev, key, "desc"))
                      }
                    />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((r) => {
                    const isOpen = expanded.has(r.id)
                    const sevs = Array.from(
                      new Set(r.issues_detail.map((i) => i.severity))
                    ).sort(
                      (a, b) =>
                        (SEVERITY_ORDER[a] ?? 9) - (SEVERITY_ORDER[b] ?? 9)
                    )
                    return (
                      <Fragment key={r.id}>
                        <TableRow
                          className="cursor-pointer"
                          onClick={() => toggleExpand(r.id)}
                        >
                          <TableCell>
                            <ChevronDown
                              className={`h-4 w-4 text-muted-foreground transition-transform ${
                                isOpen ? "" : "-rotate-90"
                              }`}
                            />
                          </TableCell>
                          <TableCell className="font-medium">
                            {r.resource_type}
                          </TableCell>
                          <TableCell>
                            <span className="font-mono text-xs">
                              {r.resource_id}
                            </span>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {sevs.map((s) => (
                                <Badge
                                  key={s}
                                  variant="outline"
                                  className={SEVERITY_STYLES[s] ?? ""}
                                >
                                  {s}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {r.issues_detail.length}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {dateFormatter.format(new Date(r.created_at))}
                          </TableCell>
                        </TableRow>

                        {isOpen && (
                          <TableRow key={`${r.id}-detail`}>
                            <TableCell colSpan={6} className="bg-muted/30 p-0">
                              <div className="space-y-4 px-4 py-4">
                                <div>
                                  <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                                    Issues
                                  </p>
                                  <ul className="space-y-1.5">
                                    {r.issues_detail.map((iss, i) => (
                                      <li
                                        key={i}
                                        className="flex flex-wrap items-center gap-2 text-sm"
                                      >
                                        <Badge
                                          variant="outline"
                                          className={
                                            SEVERITY_STYLES[iss.severity] ?? ""
                                          }
                                        >
                                          {iss.severity}
                                        </Badge>
                                        <span className="font-mono text-xs text-muted-foreground">
                                          {iss.rule}
                                        </span>
                                        <span>{iss.message}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                                {serverId && (
                                  <ResourceActions
                                    serverId={serverId}
                                    runId={runId}
                                    resource={r}
                                    fixable={r.issues_detail.some((i) =>
                                      fixableSet.has(
                                        `${r.resource_type}:${i.rule}`
                                      )
                                    )}
                                  />
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>

        {total > 0 && (
          <CardFooter className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Showing {page * PAGE_SIZE + 1}–
              {Math.min((page + 1) * PAGE_SIZE, total)} of{" "}
              {total.toLocaleString()}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0 || listQ.isFetching}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                {page + 1} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages - 1 || listQ.isFetching}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  )
}

function ResourceTypeMultiSelect({
  options,
  selected,
  onChange,
}: {
  options: Array<string>
  selected: Set<string>
  onChange: (next: Set<string>) => void
}) {
  const [open, setOpen] = useState(false)
  const label =
    selected.size === 0
      ? "All resource types"
      : selected.size === 1
        ? Array.from(selected)[0]
        : `${selected.size} resource types`

  function toggle(rt: string) {
    const next = new Set(selected)
    if (next.has(rt)) next.delete(rt)
    else next.add(rt)
    onChange(next)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
        >
          <span className="truncate">{label}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-(--radix-popover-trigger-width) p-2"
      >
        <div className="no-scrollbar max-h-68 space-y-0.5 overflow-y-auto">
          {options.map((rt) => (
            <label
              key={rt}
              className="flex cursor-pointer items-center gap-2 rounded-md p-1.5 text-sm hover:bg-muted/50"
            >
              <Checkbox
                checked={selected.has(rt)}
                onCheckedChange={() => toggle(rt)}
              />
              <span>{rt}</span>
            </label>
          ))}
        </div>
        {selected.size > 0 && (
          <>
            <Separator className="my-1.5" />
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => onChange(new Set())}
            >
              Clear selection
            </Button>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}

function ResourceActions({
  serverId,
  runId,
  resource,
  fixable,
}: {
  serverId: string
  runId: string
  resource: InvalidResourceRead
  fixable: boolean
}) {
  const qc = useQueryClient()
  const [pending, setPending] = useState<null | "fix" | "delete">(null)

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["validation", "runs", runId] })

  function handleResult(res: { error_message?: string | null } | undefined) {
    // success signal = no error_message (robust against audit-status casing)
    if (res && !res.error_message) {
      toast.success(
        `${resource.resource_type} ${resource.resource_id} updated`,
        { classNames: { icon: "text-green-500" } }
      )
      invalidate()
    } else {
      toast.custom(
        () => (
          <div className="z-50 flex w-100 flex-col gap-3 rounded-md border bg-background! p-4 shadow-lg">
            <div className="flex items-start gap-3">
              <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-red-500 text-white">
                <XIcon className="size-3.5" />
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <p className="text-sm font-semibold">Action Failed </p>
              </div>
            </div>
            <Separator className="bg-border/10" />
            <div className="text-invert-foreground/60 space-y-1 font-mono text-xs">
              <p>{res?.error_message ?? "Action failed"}</p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                className="flex-1"
                variant="outline"
                onClick={() => toast.dismiss()}
              >
                View Logs
              </Button>
              <Button
                size="sm"
                className="flex-1"
                variant="destructive"
                onClick={() => toast.dismiss()}
              >
                close
              </Button>
            </div>
          </div>
        ),
        { duration: Infinity }
      )
    }
    setPending(null)
  }

  const fixM = useMutation({
    mutationFn: () =>
      autoFixResource(serverId, resource.resource_type, resource.resource_id),
    onSuccess: handleResult,
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "Fix failed")
      setPending(null)
    },
  })

  const delM = useMutation({
    mutationFn: () =>
      deleteResource(serverId, resource.resource_type, resource.resource_id),
    onSuccess: handleResult,
    onError: (e: unknown) => {
      toast.error(" Delete failed", {
        description: e instanceof Error ? e.message : "Delete failed",
      })
      setPending(null)
    },
  })

  const busy = fixM.isPending || delM.isPending
  const fhirUrl = `${resource.server_base_url.replace(/\/$/, "")}/${resource.resource_type}/${resource.resource_id}`

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {fixable && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            className="gap-1 border-orange-500/20 text-orange-500!"
            onClick={() => setPending("fix")}
          >
            <PenNewSquareIcon className="size-4" />
            Fix
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          className="gap-1 text-red-600 hover:text-red-600 dark:text-red-400"
          onClick={() => setPending("delete")}
        >
          <TrashBinMinimalisticIcon className="size-4" />
          Delete
        </Button>
        <Button asChild size="sm" variant="outline" className="gap-1">
          <a href={fhirUrl} target="_blank" rel="noopener noreferrer">
            <LinkRoundIcon className="size-4" />
            Open on FHIR server
          </a>
        </Button>
      </div>

      <AlertDialog
        open={pending !== null}
        onOpenChange={(o) => !o && !busy && setPending(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pending === "delete"
                ? "Delete resource?"
                : "Apply automatic fix?"}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                {pending === "delete" ? (
                  <>
                    Permanently deletes{" "}
                    <span className="font-mono">
                      {resource.resource_type}/{resource.resource_id}
                    </span>{" "}
                    from the FHIR server. This cannot be undone.
                  </>
                ) : (
                  <>
                    Removes the forbidden fields from{" "}
                    <span className="font-mono">
                      {resource.resource_type}/{resource.resource_id}
                    </span>{" "}
                    using the predefined template (ETag-checked).
                  </>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy}
              className={
                pending === "delete" ? "bg-red-600 hover:bg-red-700" : ""
              }
              onClick={(e) => {
                e.preventDefault()
                if (pending === "delete") delM.mutate()
                else fixM.mutate()
              }}
            >
              {busy ? "Working..." : pending === "delete" ? "Delete" : "Fix"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
