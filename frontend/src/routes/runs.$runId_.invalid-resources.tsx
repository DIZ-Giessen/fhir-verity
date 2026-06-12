import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Sparkles,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import {
  type InvalidResourceRead,
  invalidResourcesQueryOptions,
  resourceTypesQueryOptions,
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
import {
  Select,
  SelectContent,
  SelectItem,
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
import { dateFormatter } from "@/lib/functions/runs"
import type { InvalidResourcesParams } from "@/lib/interface"
import { Restart } from "@solar-icons/react-perf/category/style/LineDuotone"

export const Route = createFileRoute("/runs/$runId_/invalid-resources")({
  component: InvalidResourcesPage,
})

const PAGE_SIZE = 25
const ALL = "all"

const SEVERITY_STYLES: Record<string, string> = {
  error:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  warning:
    "border-0 bg-amber-500/15 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
  info: "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
}
const SEVERITY_ORDER: Record<string, number> = {
  error: 0,
  warning: 1,
  info: 2,
}

function fhirResourceUrl(r: InvalidResourceRead): string {
  return `${r.server_base_url.replace(/\/$/, "")}/${r.resource_type}/${r.resource_id}`
}

function InvalidResourcesPage() {
  const { runId } = Route.useParams()

  const [page, setPage] = useState(0)
  const [resourceType, setResourceType] = useState(ALL)
  const [rule, setRule] = useState(ALL)
  const [severity, setSeverity] = useState(ALL)
  const [onlyCurrent, setOnlyCurrent] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // any filter change -> back to first page
  useEffect(() => {
    setPage(0)
  }, [resourceType, rule, severity, onlyCurrent])

  const params: InvalidResourcesParams = {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    resource_type: resourceType === ALL ? undefined : resourceType,
    rule: rule === ALL ? undefined : rule,
    severity: severity === ALL ? undefined : severity,
    only_current_run: onlyCurrent,
  }

  const listQ = useQuery(invalidResourcesQueryOptions(runId, params))
  const typesQ = useQuery(resourceTypesQueryOptions())
  const summaryQ = useQuery(runSummaryQueryOptions(runId))

  const ruleOptions = useMemo(() => {
    const set = new Set<string>()
    for (const rt of summaryQ.data?.by_resource_type ?? [])
      for (const r of rt.by_rule) set.add(r.rule)
    return Array.from(set).sort()
  }, [summaryQ.data])

  const items = listQ.data?.items ?? []
  const total = listQ.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters = resourceType !== ALL || rule !== ALL || severity !== ALL

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
          <div className="flex flex-wrap items-center gap-2">
            <Select value={resourceType} onValueChange={setResourceType}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Resource type" />
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

            <Select value={rule} onValueChange={setRule}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Rule" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All rules</SelectItem>
                {ruleOptions.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={severity} onValueChange={setSeverity}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All severities</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>

            <label className="flex items-center gap-2 text-sm">
              <Switch checked={onlyCurrent} onCheckedChange={setOnlyCurrent} />
              Only this run
            </label>

            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setResourceType(ALL)
                  setRule(ALL)
                  setSeverity(ALL)
                }}
              >
                Reset
                <Restart className="ml-1 h-4 w-4" />
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
                    <TableHead>Resource type</TableHead>
                    <TableHead>Resource ID</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead className="text-right">Issues</TableHead>
                    <TableHead>Detected</TableHead>
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
                      <>
                        <TableRow
                          key={r.id}
                          className="cursor-pointerl"
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

                                <div className="rounded-lg border border-dashed p-3">
                                  <div className="mt-2 flex gap-2">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled
                                      className="gap-1"
                                    >
                                      <Sparkles className="h-3.5 w-3.5" />
                                      Suggest fix
                                    </Button>
                                    <Button
                                      asChild
                                      size="sm"
                                      variant="outline"
                                      className="gap-1"
                                    >
                                      <a
                                        href={fhirResourceUrl(r)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                      >
                                        <ExternalLink className="h-3.5 w-3.5" />
                                        Open on FHIR server
                                      </a>
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </>
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
