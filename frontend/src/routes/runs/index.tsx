import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight, Play } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import {
  Documents,
  InfoCircle,
  NotificationLinesRemove,
  SquareTopDown,
} from "@solar-icons/react-perf/category/style/LineDuotone"
import type { MonthlyBucket, TestReportSummary } from "@/lib/interface"
import type { ValidationRunListItem } from "@/api/queries"
import { AreaChart } from "@/components/charts/area-chart"
import { Area } from "@/components/charts/area"
import { XAxis } from "@/components/charts/x-axis"
import { Grid } from "@/components/charts/grid"
import { ChartTooltip } from "@/components/charts/tooltip"

import { runsQueryOptions, serversQueryOptions } from "@/api/queries"
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  RUN_STATUS_STYLES,
  dateFormatter,
  formatDuration,
  monthLabelFormatter,
} from "@/lib/functions/runs"
import { StartValidationDialog } from "@/components/start-validation-dialog"
import { TextDots } from "@/components/text-dots"

export const Route = createFileRoute("/runs/")({ component: RunsPage })

type RunWithReport = ValidationRunListItem & {
  test_report?: TestReportSummary | null
}

function bucketByMonth(
  runs: Array<ValidationRunListItem> | undefined,
  months: number
): Array<MonthlyBucket> {
  const now = new Date()
  const buckets: Array<MonthlyBucket> = []
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    buckets.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: monthLabelFormatter.format(d),
      date: new Date(d.getFullYear(), d.getMonth(), 1), // neu
      invalid: 0,
      runs: 0,
    })
  }
  const lookup = new Map(buckets.map((b) => [b.key, b]))

  for (const r of runs ?? []) {
    if (r.status !== "completed") continue
    const d = new Date(r.started_at)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    const bucket = lookup.get(key)
    if (bucket) {
      bucket.invalid += r.total_invalid
      bucket.runs += 1
    }
  }
  return buckets
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function RunsPage() {
  const runsQ = useQuery(runsQueryOptions(500))
  const serversQ = useQuery(serversQueryOptions())

  const [_setMenuOpen, setMenuOpen] = useState(false)
  const [startOpen, setStartOpen] = useState(false)
  const serverMap = useMemo(() => {
    const map = new Map<
      string,
      { id: string; name: string; base_url: string }
    >()
    serversQ.data?.forEach((s) =>
      map.set(s.id, { id: s.id, name: s.name, base_url: s.base_url })
    )
    return map
  }, [serversQ.data])

  const monthly = useMemo(
    () => bucketByMonth(runsQ.data?.items, 8),
    [runsQ.data]
  )

  const totalRuns = monthly.reduce((sum, b) => sum + b.runs, 0)

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Validation runs
            </h1>
            <p className="text-sm text-muted-foreground">
              History of all validation runs across servers, with links to the
              FHIR resources they produced.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              className=""
              onClick={() => {
                setMenuOpen(false)
                setStartOpen(true)
              }}
            >
              <Play className="size-4" />
              Start a new run
            </Button>
          </div>
        </div>

        <BarCard
          data={monthly}
          totalRuns={totalRuns}
          loading={runsQ.isPending}
        />

        <RunsTable
          runs={runsQ.data?.items ?? []}
          serverMap={serverMap}
          loading={runsQ.isPending}
        />
      </div>
      <StartValidationDialog open={startOpen} onOpenChange={setStartOpen} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function BarCard({
  data,
  totalRuns,
  loading,
}: {
  data: Array<MonthlyBucket>
  totalRuns: number
  loading: boolean
}) {
  return (
    <div className="border-none shadow-none">
      {/*  <CardHeader className="items-center">
        <CardTitle className="text-base">
          Validation activity — last 8 months
        </CardTitle>
        <CardDescription>Number of completed runs per month.</CardDescription>
      </CardHeader> */}
      <div className="pb-0">
        {loading ? (
          <Skeleton className="h-65 w-full" />
        ) : (
          <div className="w-full">
            <AreaChart
              className="max-h-96"
              data={data.map((b) => ({ ...b, date: b.date.toISOString() }))}
              xDataKey="date"
              aspectRatio="2 / 1"
              margin={{ top: 8, right: 12, bottom: 32, left: 40 }}
            >
              <Grid horizontal />
              <Area
                dataKey="runs"
                fill="hsl(24.6 95% 53.1%)"
                fillOpacity={0.2}
                fadeEdges
              />
              <XAxis numTicks={8} />
              <ChartTooltip />
            </AreaChart>
          </div>
        )}
      </div>
      <CardFooter className="text-sm text-muted-foreground">
        {totalRuns} total runs across the window
      </CardFooter>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Runs table
// ---------------------------------------------------------------------------

/* {
 


} */

const PAGE_SIZE = 10

function RunsTable({
  runs,
  serverMap,
  loading,
}: {
  runs: Array<ValidationRunListItem>
  serverMap: Map<string, { id: string; name: string; base_url: string }>
  loading: boolean
}) {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return runs.filter((r) => {
      if (statusFilter !== "all" && r.status !== statusFilter) return false
      if (q) {
        const name = serverMap.get(r.server_id)?.name.toLowerCase() ?? ""
        if (!name.includes(q)) return false
      }
      return true
    })
  }, [runs, statusFilter, search, serverMap])

  // Filterwechsel -> immer zurück auf Seite 1
  useEffect(() => {
    setPage(0)
  }, [statusFilter, search])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageStart = page * PAGE_SIZE
  const pageEnd = pageStart + PAGE_SIZE
  const pageItems = filtered.slice(pageStart, pageEnd)

  return (
    <Card className="shadow-2xs">
      <CardHeader className="gap-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">All runs</CardTitle>
          <p className="text-xs text-muted-foreground">
            {filtered.length} of {runs.length}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            placeholder="Search by server name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sm:max-w-xs"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>

      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {runs.length === 0
              ? "No validation runs yet."
              : "No runs match the current filters."}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Started by</TableHead>
                <TableHead>Server</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">Processed</TableHead>
                <TableHead className="text-right">Invalid</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead>FHIR resources</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageItems.map((r) => {
                const server = serverMap.get(r.server_id)
                const rate =
                  r.total_processed > 0
                    ? (r.total_invalid / r.total_processed) * 100
                    : null
                const tr = (r as RunWithReport).test_report
                return (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={RUN_STATUS_STYLES[r.status] ?? ""}
                      >
                        {r.status === "running" ? (
                          <TextDots>Running</TextDots>
                        ) : (
                          r.status
                        )}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {dateFormatter.format(new Date(r.started_at))}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {r.triggered_by?.full_name ??
                        r.triggered_by?.username ??
                        "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {server ? (
                        <Link
                          to="/servers/$id"
                          params={{ id: server.id }}
                          className="hover:underline"
                        >
                          {server.name}
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">unknown</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDuration(r.started_at, r.finished_at)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.total_processed.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.total_invalid.toLocaleString()}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right font-medium tabular-nums",
                        rate == null
                          ? "text-muted"
                          : rate < 10
                            ? "text-emerald-500"
                            : rate < 30
                              ? "text-orange-500"
                              : "text-rose-500"
                      )}
                    >
                      {rate != null ? `${rate.toFixed(1)}%` : "—"}
                    </TableCell>
                    <TableCell>
                      <FhirResourcesPopover
                        baseUrl={server?.base_url}
                        report={tr ?? null}
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        asChild
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                      >
                        <Link to="/runs/$runId" params={{ runId: r.id }}>
                          <ChevronRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {filtered.length > PAGE_SIZE && (
        <CardFooter className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Showing {pageStart + 1}–{Math.min(pageEnd, filtered.length)} of{" "}
            {filtered.length}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="size-4" />
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              {page + 1} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              Next
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  )
}
// ---------------------------------------------------------------------------
// FHIR resources popover
// ---------------------------------------------------------------------------

export function FhirResourcesPopover({
  baseUrl,
  report,
}: {
  baseUrl: string | undefined
  report: TestReportSummary | null
}) {
  if (!report || !baseUrl) {
    return (
      <Button variant="ghost" size="sm" disabled className="h-7 gap-1">
        <NotificationLinesRemove className="size-4.5" />
        <span>Not available</span>
      </Button>
    )
  }

  const base = baseUrl.replace(/\/$/, "")
  const vrId = report.verification_result?.server_id
  const scripts = Object.entries(report.test_scripts ?? {})
    .map(([rt, info]) => ({ rt, id: info.server_id }))
    .filter((x): x is { rt: string; id: string } => Boolean(x.id))
  const reports = Object.entries(report.test_reports ?? {})
    .map(([rt, info]) => ({ rt, id: info.server_id }))
    .filter((x): x is { rt: string; id: string } => Boolean(x.id))

  const empty = !vrId && scripts.length === 0 && reports.length === 0

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-7 gap-1">
          <Documents className="size-4.5" />
          <span className="text-xs text-muted-foreground">View Resources</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 p-0">
        <div className="max-h-96 overflow-y-auto p-4">
          {empty && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <InfoCircle className="size-4 shrink-0" />
              {report.posted_to_server === false
                ? "Writing FHIR reports was disabled for this server, so no resources were created on it."
                : "Reports were not successfully posted to the FHIR server."}
            </p>
          )}

          {vrId && (
            <section>
              <Label className="py-2 text-xs text-orange-500/80">
                VerificationResult
              </Label>
              <ResourceLink
                href={`${base}/VerificationResult/${vrId}`}
                label="View on FHIR server"
              />
            </section>
          )}

          {reports.length > 0 && (
            <section>
              <Label className="py-2 text-xs text-rose-500/80">
                TestReports
              </Label>
              <ul className="space-y-1">
                {reports.map(({ rt, id }) => (
                  <li key={rt}>
                    <ResourceLink
                      href={`${base}/TestReport/${id}`}
                      label={rt}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {scripts.length > 0 && (
            <section>
              <Label className="py-2 text-xs text-blue-500/80">
                TestScripts
              </Label>
              <ul className="space-y-1">
                {scripts.map(({ rt, id }) => (
                  <li key={rt}>
                    <ResourceLink
                      href={`${base}/TestScript/${id}`}
                      label={rt}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function ResourceLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between gap-2 rounded-xl border bg-accent px-2 py-1.5 text-xs hover:bg-muted/50"
    >
      <span className="font-medium">{label}</span>
      <SquareTopDown className="size-3 text-muted-foreground" />
    </a>
  )
}
