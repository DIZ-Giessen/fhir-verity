import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { Activity, AlertTriangle, ArrowRight, ChevronLeft } from "lucide-react"
import { useMemo } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  XAxis,
  YAxis,
} from "recharts"

import {
  type PerResourceStats,
  runQueryOptions,
  runSummaryQueryOptions,
  serverQueryOptions,
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { FhirResourcesPopover } from "./runs.index"
import {
  dateFormatter,
  formatDuration,
  RUN_STATUS_STYLES,
} from "@/lib/functions/runs"
import type { TestReportSummary } from "@/lib/interface"
import {
  ArrowRightUp,
  CheckCircle,
  DangerTriangle,
  SadCircle,
  Star2,
} from "@solar-icons/react-perf/category/style/LineDuotone"

export const Route = createFileRoute("/runs/$runId")({
  component: RunDetailPage,
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SEVERITY_STYLES: Record<string, string> = {
  error:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  warning:
    "border-0 bg-amber-500/15 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
  info: "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
}

// Invalid-rate -> gauge colour band (matches the palette used in runs.tsx)
function gaugeColor(rate: number): string {
  if (rate >= 0.25) return "hsl(0 72% 51%)"
  if (rate >= 0.05) return "hsl(38 92% 50%)"
  if (rate === 0) return "hsl(142 71% 45%)"
  return "hsl(142 71% 45%)"
}

const barConfig = {
  processed: { label: "Processed", color: "hsl(217 91% 60%)" },
  invalid: { label: "Invalid", color: "hsl(0 72% 51%)" },
} satisfies ChartConfig

const gaugeConfig = {
  value: { label: "Invalid rate" },
} satisfies ChartConfig

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function RunDetailPage() {
  const { runId } = Route.useParams()

  const runQ = useQuery({
    ...runQueryOptions(runId),
    // poll while the run is still in progress, stop once it settles
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5000 : false),
  })
  const summaryQ = useQuery(runSummaryQueryOptions(runId))

  const run = runQ.data
  const serverQ = useQuery({
    ...serverQueryOptions(run?.server_id ?? ""),
    enabled: Boolean(run?.server_id),
  })

  const ruleRows = useMemo(() => {
    const rows: {
      resourceType: string
      rule: string
      severity: string
      count: number
    }[] = []
    for (const rt of summaryQ.data?.by_resource_type ?? []) {
      for (const r of rt.by_rule) {
        rows.push({
          resourceType: rt.resource_type,
          rule: r.rule,
          severity: r.severity,
          count: r.count,
        })
      }
    }
    return rows.sort((a, b) => b.count - a.count)
  }, [summaryQ.data])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          to="/runs"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back to runs
        </Link>
        <Button asChild size="sm">
          <Link
            to="/runs/$runId/invalid-resources"
            params={{ runId: run?.id ?? "" }}
          >
            View all invalid resources
            <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
      </div>

      {runQ.isPending ? (
        <DetailSkeleton />
      ) : runQ.isError || !run ? (
        <Card className="border-red-500/30">
          <CardContent className="flex items-start gap-3 py-6">
            <DangerTriangle className="size-8 text-rose-500" strokeWidth={3} />
            <div>
              <p className="text-sm font-medium">Could not load this run.</p>
              <p className="text-xs text-muted-foreground">
                The run may have been deleted, or the ID is invalid.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* --- Header --------------------------------------------------- */}
          <Card className="shadow-2xs">
            <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-xl">Validation run</CardTitle>
                  <Badge
                    variant="outline"
                    className={RUN_STATUS_STYLES[run.status] ?? ""}
                  >
                    {run.status === "running" ? (
                      <Star2 className="scale-115 animate-spin" />
                    ) : run.status === "failed" ? (
                      <SadCircle className="scale-125" />
                    ) : (
                      <CheckCircle className="scale-125" />
                    )}
                    {run.status}{" "}
                  </Badge>
                </div>
                <p className="font-mono text-xs text-muted-foreground">
                  {run.id}
                </p>
                <p className="text-sm text-muted-foreground">
                  Server:{" "}
                  {serverQ.data ? (
                    <Link
                      to="/servers/$id"
                      params={{ id: serverQ.data.id }}
                      className="inline-flex items-center gap-1 font-medium text-foreground hover:underline"
                    >
                      {serverQ.data.name}
                      <ArrowRightUp className="size-4" />
                    </Link>
                  ) : (
                    <span>—</span>
                  )}
                </p>
              </div>
              <FhirResourcesPopover
                baseUrl={serverQ.data?.base_url}
                report={(run.test_report ?? null) as TestReportSummary | null}
              />
            </CardHeader>

            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
                <MetaItem label="Started">
                  {dateFormatter.format(new Date(run.started_at))}
                </MetaItem>
                <MetaItem label="Finished">
                  {run.finished_at
                    ? dateFormatter.format(new Date(run.finished_at))
                    : "—"}
                </MetaItem>
                <MetaItem label="Duration">
                  {run.status === "running"
                    ? "running…"
                    : formatDuration(run.started_at, run.finished_at)}
                </MetaItem>
                <MetaItem label="Processed">
                  <span className="tabular-nums">
                    {run.total_processed.toLocaleString()}
                  </span>
                </MetaItem>
                <MetaItem label="Invalid">
                  <span className="tabular-nums">
                    {run.total_invalid.toLocaleString()}
                  </span>
                </MetaItem>
                <MetaItem label="Invalid rate">
                  <span className="tabular-nums">
                    {(
                      (summaryQ.data?.overall_invalid_rate ??
                        (run.total_processed > 0
                          ? run.total_invalid / run.total_processed
                          : 0)) * 100
                    ).toFixed(1)}
                    %
                  </span>
                </MetaItem>
              </dl>

              {run.resource_types.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {run.resource_types.map((rt) => (
                    <Badge key={rt} variant="secondary" className="font-normal">
                      {rt}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* --- Running / failed banners -------------------------------- */}
          {run.status === "running" && (
            <Card className="border-blue-500/30 bg-blue-500/5">
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <div className="flex items-center gap-3">
                  <Activity className="h-5 w-5 animate-pulse text-blue-500" />
                  <div>
                    <p className="text-sm font-medium">
                      This run is still in progress.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Numbers refresh automatically every few seconds.
                    </p>
                  </div>
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link to="/runs/$runId/live" params={{ runId: run.id }}>
                    Live view
                    <ArrowRightUp className="ml-1 size-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}

          {run.status === "failed" && run.error_message && (
            <Card className="border-rose-500/30 bg-rose-500/5">
              <CardContent className="flex items-start gap-3 py-4">
                <AlertTriangle className="mt-0.5 h-5 w-5 text-rose-500" />
                <div>
                  <p className="text-sm font-medium">Run failed</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {run.error_message}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* --- Bar chart: processed vs invalid per type ---------------- */}
          <Card className="">
            <CardHeader>
              <CardTitle className="text-base">Resources by type</CardTitle>
              <CardDescription>
                Processed and invalid counts for each validated resource type.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {run.per_resource_stats.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No per-type statistics for this run yet.
                </p>
              ) : (
                <ChartContainer config={barConfig} className="h-[280px] w-full">
                  <BarChart
                    accessibilityLayer={false}
                    data={run.per_resource_stats.map((s) => ({
                      type: s.resource_type,
                      processed: s.processed,
                      invalid: s.invalid,
                    }))}
                    margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey="type"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={10}
                      fontSize={12}
                    />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      width={44}
                    />
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent />}
                    />
                    <Bar
                      dataKey="processed"
                      fill="var(--color-processed)"
                      radius={[8, 8, 0, 0]}
                      type="number"
                    />
                    <Bar
                      dataKey="invalid"
                      fill="var(--color-invalid)"
                      radius={[8, 8, 0, 0]}
                      type="number"
                    />
                  </BarChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          {/* --- Radial gauges: invalid rate per type -------------------- */}
          {run.per_resource_stats.length > 0 && (
            <div>
              <h2 className="mb-3 text-base font-medium">
                Invalid rate per resource type
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {run.per_resource_stats.map((s) => (
                  <RateGauge key={s.resource_type} stat={s} />
                ))}
              </div>
            </div>
          )}

          {/* --- Per-rule breakdown -------------------------------------- */}
          <Card className="shadow-2xs">
            <CardHeader>
              <CardTitle className="text-base">Rule violations</CardTitle>
              <CardDescription>
                Which rules were violated, by resource type, most frequent
                first.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {summaryQ.isPending ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              ) : ruleRows.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No rule violations recorded.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Resource type</TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ruleRows.map((row) => (
                      <TableRow key={`${row.resourceType}:${row.rule}`}>
                        <TableCell className="font-medium">
                          {row.resourceType}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {row.rule}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={SEVERITY_STYLES[row.severity] ?? ""}
                          >
                            {row.severity}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.count.toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
            <CardFooter className="justify-end">
              <Button asChild>
                <Link
                  to="/runs/$runId/invalid-resources"
                  params={{ runId: run.id }}
                >
                  View invalid resources
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardFooter>
          </Card>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetaItem({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

function RateGauge({ stat }: { stat: PerResourceStats }) {
  const pct = Math.round(stat.invalid_rate * 1000) / 10
  const fill = gaugeColor(stat.invalid_rate)
  const data = [
    {
      name: stat.resource_type,
      value: Math.min(100, stat.invalid_rate * 100),
      fill,
    },
  ]

  return (
    <Card className="p-4">
      <CardContent className="flex items-center gap-4 p-0">
        <div className="relative flex items-center justify-center">
          <ChartContainer config={gaugeConfig} className="h-[95px] w-[95px]">
            <RadialBarChart
              data={data}
              innerRadius={30}
              outerRadius={60}
              barSize={6}
              startAngle={90}
              endAngle={-270}
            >
              <PolarAngleAxis
                type="number"
                domain={[0, 100]}
                angleAxisId={0}
                tick={false}
                axisLine={false}
              />
              <RadialBar
                dataKey="value"
                background={{ fill: "var(--muted)" }}
                cornerRadius={10}
                angleAxisId={0}
              />
            </RadialBarChart>
          </ChartContainer>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-sm font-medium">{pct}%</span>
          </div>
        </div>
        <div>
          <dt className="text-sm font-medium">{stat.resource_type}</dt>
          <dd className="text-sm text-muted-foreground">
            {stat.invalid.toLocaleString()} of {stat.processed.toLocaleString()}{" "}
            invalid
          </dd>
        </div>
      </CardContent>
    </Card>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Card className="shadow-2xs">
        <CardHeader className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-3 w-64" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
      <Skeleton className="h-[340px] w-full rounded-xl" />
    </div>
  )
}
