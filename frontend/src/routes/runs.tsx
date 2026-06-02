import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ChevronRight,
  ExternalLink,
  FileText,
  Search,
  Shield,
} from "lucide-react"
import { useMemo } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
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

function RunsTable({
  runs,
  serverMap,
  loading,
}: {
  runs: ValidationRunListItem[]
  serverMap: Map<string, { id: string; name: string; base_url: string }>
  loading: boolean
}) {
  return (
    <Card className="shadow-2xs">
      <CardHeader>
        <CardTitle className="text-base">All runs</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No validation runs yet.
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
              {runs.map((r) => {
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
                    <TableCell className="text-right tabular-nums">
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
      <Button variant="outline" size="sm" disabled className="h-7 gap-1">
        <FileText className="h-3 w-3" />
        <span className="text-xs">—</span>
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
        <Button variant="outline" size="sm" className="h-7 gap-1">
          <FileText className="h-3 w-3" />
          <span className="text-xs">View</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 p-0">
        <div className="max-h-96 space-y-3 overflow-y-auto p-4">
          {empty && (
            <p className="text-sm text-muted-foreground">
              Reports were not successfully posted to the FHIR server.
            </p>
          )}

          {vrId && (
            <section>
              <SectionLabel icon={Shield}>VerificationResult</SectionLabel>
              <ResourceLink
                href={`${base}/VerificationResult/${vrId}`}
                label="View on FHIR server"
              />
            </section>
          )}

          {scripts.length > 0 && (
            <section>
              <SectionLabel icon={FileText}>TestScripts</SectionLabel>
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

          {reports.length > 0 && (
            <section>
              <SectionLabel icon={Search}>TestReports</SectionLabel>
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
        </div>
      </PopoverContent>
    </Popover>
  )
}

function SectionLabel({
  icon: Icon,
  children,
}: {
  icon: typeof FileText
  children: React.ReactNode
}) {
  return (
    <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
      <Icon className="h-3 w-3" />
      {children}
    </div>
  )
}

function ResourceLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between gap-2 rounded-md border px-2 py-1.5 text-xs hover:bg-muted/50"
    >
      <span className="font-medium">{label}</span>
      <ExternalLink className="h-3 w-3 text-muted-foreground" />
    </a>
  )
}
