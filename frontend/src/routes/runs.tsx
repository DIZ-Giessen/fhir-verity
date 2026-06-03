import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  XAxis,
  YAxis,
} from "recharts"

import {
  type ValidationRunListItem,
  runsQueryOptions,
  serversQueryOptions,
} from "@/api/queries"
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
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
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
import {
  CheckCircle,
  Documents,
  NotificationLinesRemove,
  SadCircle,
  SquareTopDown,
  Star2,
} from "@solar-icons/react-perf/category/style/LineDuotone"
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

export const Route = createFileRoute("/runs")({ component: RunsPage })

// ---------------------------------------------------------------------------
// Types — shape of the `test_report` JSON written by fhir_report_service.py
// ---------------------------------------------------------------------------

interface ResourceRef {
  local_id?: string
  server_id?: string | null
  url?: string
}

interface TestReportEntry extends ResourceRef {
  result?: string
  score?: number
  violation_counts?: Record<string, number>
}

interface TestReportSummary {
  run_id?: string
  generated_at?: string
  test_scripts?: Record<string, ResourceRef>
  test_reports?: Record<string, TestReportEntry>
  verification_result?: {
    local_id?: string
    server_id?: string | null
    status?: string
    has_errors?: boolean
  } | null
}

type RunWithReport = ValidationRunListItem & {
  test_report?: TestReportSummary | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

const monthLabelFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
})

function formatDuration(startISO: string, endISO: string | null): string {
  if (!endISO) return "—"
  const sec = Math.round(
    (new Date(endISO).getTime() - new Date(startISO).getTime()) / 1000
  )
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}m ${sec % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

interface MonthlyBucket {
  key: string
  label: string
  invalid: number
  runs: number
}

function bucketByMonth(
  runs: ValidationRunListItem[] | undefined,
  months: number
): MonthlyBucket[] {
  const now = new Date()
  const buckets: MonthlyBucket[] = []
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    buckets.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: monthLabelFormatter.format(d),
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

const RUN_STATUS_STYLES: Record<string, string> = {
  completed:
    "border-0 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
  running:
    "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
  failed:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function RunsPage() {
  const runsQ = useQuery(runsQueryOptions(50))
  const serversQ = useQuery(serversQueryOptions())

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

  const totalInvalid = monthly.reduce((sum, b) => sum + b.invalid, 0)
  const totalRuns = monthly.reduce((sum, b) => sum + b.runs, 0)

  return (
    <div className="space-y-6">
      <div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Validation runs
          </h1>
          <p className="text-sm text-muted-foreground">
            History of all validation runs across servers, with links to the
            FHIR resources they produced.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <RadarCard
          data={monthly}
          totalInvalid={totalInvalid}
          loading={runsQ.isPending}
        />
        <BarCard
          data={monthly}
          totalRuns={totalRuns}
          loading={runsQ.isPending}
        />
      </div>

      <RunsTable
        runs={runsQ.data?.items ?? []}
        serverMap={serverMap}
        loading={runsQ.isPending}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

const radarConfig = {
  invalid: { label: "Invalid", color: "hsl(0 72% 51%)" },
} satisfies ChartConfig

function RadarCard({
  data,
  totalInvalid,
  loading,
}: {
  data: MonthlyBucket[]
  totalInvalid: number
  loading: boolean
}) {
  return (
    <Card className="shadow-2xs">
      <CardHeader className="items-center">
        <CardTitle className="text-base">
          Invalid resources — last 8 months
        </CardTitle>
        <CardDescription>
          Sum of invalid resources per month across completed runs.
        </CardDescription>
      </CardHeader>
      <CardContent className="pb-0">
        {loading ? (
          <Skeleton className="mx-auto aspect-square max-h-[260px] w-full max-w-[300px]" />
        ) : (
          <ChartContainer
            config={radarConfig}
            className="mx-auto aspect-square max-h-[260px]"
          >
            <RadarChart data={data}>
              <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
              <PolarAngleAxis dataKey="label" />
              <PolarGrid />
              <Radar
                dataKey="invalid"
                fill="var(--color-invalid)"
                fillOpacity={0.6}
                dot={{ r: 4, fillOpacity: 1 }}
              />
            </RadarChart>
          </ChartContainer>
        )}
      </CardContent>
      <CardFooter className="text-sm text-muted-foreground">
        {totalInvalid.toLocaleString()} total invalid across the window
      </CardFooter>
    </Card>
  )
}

const barConfig = {
  runs: { label: "Runs", color: "hsl(24.6 95% 53.1%)" },
} satisfies ChartConfig

function BarCard({
  data,
  totalRuns,
  loading,
}: {
  data: MonthlyBucket[]
  totalRuns: number
  loading: boolean
}) {
  return (
    <Card className="shadow-2xs">
      <CardHeader className="items-center">
        <CardTitle className="text-base">
          Validation activity — last 8 months
        </CardTitle>
        <CardDescription>Number of completed runs per month.</CardDescription>
      </CardHeader>
      <CardContent className="pb-0">
        {loading ? (
          <Skeleton className="h-[260px] w-full" />
        ) : (
          <ChartContainer config={barConfig} className="h-[260px] w-full">
            <AreaChart
              accessibilityLayer
              data={data}
              margin={{
                left: 12,
                right: 12,
              }}
            >
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={28}
              />
              <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
              <Area
                dataKey="runs"
                type="bump"
                fill="var(--color-runs)"
                stroke="var(--color-runs)"
                fillOpacity={0.2}
                stackId="a"
                /*  radius={[6, 6, 0, 0]} */
              />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
      <CardFooter className="text-sm text-muted-foreground">
        {totalRuns} total runs across the window
      </CardFooter>
    </Card>
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
  runs: ValidationRunListItem[]
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
                          <Star2 className="scale-115 animate-spin" />
                        ) : r.status === "failed" ? (
                          <SadCircle className="scale-125" />
                        ) : (
                          <CheckCircle className="scale-125" />
                        )}
                        {r.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {dateFormatter.format(new Date(r.started_at))}
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

function FhirResourcesPopover({
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
    .map(([rt, info]) => ({ rt, id: info?.server_id }))
    .filter((x): x is { rt: string; id: string } => Boolean(x.id))
  const reports = Object.entries(report.test_reports ?? {})
    .map(([rt, info]) => ({ rt, id: info?.server_id }))
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
            <p className="text-sm text-muted-foreground">
              Reports were not successfully posted to the FHIR server.
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
