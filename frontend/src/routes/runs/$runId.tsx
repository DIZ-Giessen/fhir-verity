import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { toPng } from "html-to-image"
import { useMemo, useRef, useState } from "react"
import { AlertTriangle, ArrowRight, ChevronLeft, WifiOff } from "lucide-react"
import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts"

import {
  ArrowRightUpIcon,
  CourseUpIcon,
  DangerTriangleIcon,
  ExportIcon,
  PieChart2Icon,
  RestartCircleIcon,
} from "@solar-icons/react/line-duotone"
import { toast } from "sonner"
import { FhirResourcesPopover } from "./index"
import type { PerResourceStats } from "@/api/queries"
import type { ChartConfig } from "@/components/ui/chart"
import { BarChart } from "@/components/charts/bar-chart"
import { Bar } from "@/components/charts/bar"
import { BarXAxis } from "@/components/charts/bar-x-axis"
import { Grid } from "@/components/charts/grid"
import { ChartTooltip } from "@/components/charts/tooltip"

import {
  cancelValidation,
  resumeValidation,
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
import { ChartContainer } from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { SortableTableHead, nextSort } from "@/components/sortable-table-head"
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import {
  RUN_STATUS_STYLES,
  dateFormatter,
  formatDuration,
} from "@/lib/functions/runs"
import { isServerUnresponsiveError } from "@/lib/run-errors"
import { SEVERITY_ORDER, SEVERITY_STYLES } from "@/lib/severity"
import { cn } from "@/lib/utils"

import { apiErrorMessage } from "@/lib/api-client"
import { ValueYAxis } from "@/components/charts/value-y-axis"
import { TextDots } from "@/components/text-dots"
import { Dots } from "@/components/dots"

export const Route = createFileRoute("/runs/$runId")({
  component: RunDetailPage,
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Invalid-rate -> gauge colour band (matches the palette used in runs.tsx)
function gaugeColor(rate: number): string {
  if (rate >= 0.25) return "hsl(0 72% 51%)"
  if (rate >= 0.05) return "hsl(38 92% 50%)"
  if (rate === 0) return "hsl(142 71% 45%)"
  return "hsl(142 71% 45%)"
}

const gaugeConfig = {
  value: { label: "Invalid rate" },
} satisfies ChartConfig

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function RunDetailPage() {
  const { runId } = Route.useParams()
  const [showBar, setShowBar] = useState(false)
  const chartRef = useRef<HTMLDivElement>(null)
  const runQ = useQuery({
    ...runQueryOptions(runId),
    // poll while the run is still in progress, stop once it settles
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5000 : false),
  })
  const summaryQ = useQuery(runSummaryQueryOptions(runId))

  const queryClient = useQueryClient()

  const resumeMutation = useMutation({
    mutationFn: () => resumeValidation(runId),
    onSuccess: () => {
      toast.success("Resuming run…")
      queryClient.invalidateQueries({
        queryKey: runQueryOptions(runId).queryKey,
      })
    },
    onError: (e) =>
      toast.error("Could not resume run", {
        description: apiErrorMessage(e),
      }),
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelValidation(runId),
    onSuccess: () => {
      toast.success("Stop requested…")
      queryClient.invalidateQueries({
        queryKey: runQueryOptions(runId).queryKey,
      })
    },
    onError: (e) =>
      toast.error("Could not stop run", {
        description: apiErrorMessage(e),
      }),
  })
  const run = runQ.data
  const serverQ = useQuery({
    ...serverQueryOptions(run?.server_id ?? ""),
    enabled: Boolean(run?.server_id),
  })
  const canWrite = serverQ.data?.can_write ?? false

  const [ruleSort, setRuleSort] = useState<{
    key: string
    dir: "asc" | "desc"
  }>({ key: "count", dir: "desc" })

  const ruleRows = useMemo(() => {
    const rows: Array<{
      resourceType: string
      rule: string
      severity: string
      count: number
    }> = []
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
    const dir = ruleSort.dir === "asc" ? 1 : -1
    return rows.sort((a, b) => {
      switch (ruleSort.key) {
        case "resourceType":
          return dir * a.resourceType.localeCompare(b.resourceType)
        case "rule":
          return dir * a.rule.localeCompare(b.rule)
        case "severity":
          return (
            dir *
            ((SEVERITY_ORDER[a.severity] ?? 9) -
              (SEVERITY_ORDER[b.severity] ?? 9))
          )
        default:
          return dir * (a.count - b.count)
      }
    })
  }, [summaryQ.data, ruleSort])

  const exportAsPNG = async () => {
    if (!chartRef.current) return
    try {
      const dataUrl = await toPng(chartRef.current, {
        cacheBust: true,
        pixelRatio: 2, // schärfer für Retina / zum Teilen
        backgroundColor: getComputedStyle(document.body).backgroundColor,
      })
      const link = document.createElement("a")
      link.download = `run-${run?.id ?? "chart"}.png`
      link.href = dataUrl
      link.click()
      toast.success("Chart exported as PNG")
    } catch (e) {
      toast.error("Export failed", { description: String(e) })
    }
  }

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
        {canWrite &&
        (run?.status === "failed" || run?.status === "cancelled") ? (
          <Button
            size="sm"
            onClick={() => resumeMutation.mutate()}
            disabled={resumeMutation.isPending}
          >
            {resumeMutation.isPending ? (
              <Dots className="w-7" />
            ) : (
              <>
                <RestartCircleIcon className="mr-1 size-5" />
                Restart this run
              </>
            )}
          </Button>
        ) : (
          <Button asChild size="sm">
            <Link
              to="/runs/$runId/invalid-resources"
              params={{ runId: run?.id ?? "" }}
            >
              View all invalid resources
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        )}
      </div>

      {runQ.isPending ? (
        <DetailSkeleton />
      ) : runQ.isError || !run ? (
        <Card className="border-red-500/30 shadow-2xs">
          <CardContent className="flex items-start gap-3 py-6">
            <DangerTriangleIcon
              className="size-8 text-rose-500"
              strokeWidth={3}
            />
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
          {/* --- Running / failed banners -------------------------------- */}
          {run.status === "running" && (
            <Card className="sticky top-16 z-10 bg-background shadow-2xs">
              <CardContent className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="animate-pulse">
                    <Dots className="w-10 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      This run is still in progress. The page refreshes
                      automatically every few seconds.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {canWrite && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => cancelMutation.mutate()}
                      disabled={
                        cancelMutation.isPending || run.cancel_requested
                      }
                    >
                      {run.cancel_requested ? (
                        <TextDots>Stopping</TextDots>
                      ) : (
                        "Stop"
                      )}
                    </Button>
                  )}
                  <Button
                    asChild
                    variant="outline"
                    className="text-blue-500 hover:text-blue-500/80"
                  >
                    <Link to="/runs/$runId/live" params={{ runId: run.id }}>
                      Live view
                      <ArrowRightUpIcon className="ml-1 size-4" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

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
                      <ArrowRightUpIcon className="size-4" />
                    </Link>
                  ) : (
                    <span>—</span>
                  )}
                </p>
              </div>
              <FhirResourcesPopover
                baseUrl={serverQ.data?.base_url}
                report={run.test_report ?? null}
              />
            </CardHeader>

            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-7">
                <MetaItem label="Started">
                  {dateFormatter.format(new Date(run.started_at))}
                </MetaItem>
                <MetaItem label="Finished">
                  {run.finished_at
                    ? dateFormatter.format(new Date(run.finished_at))
                    : "—"}
                </MetaItem>
                <MetaItem label="Started by">
                  {run.triggered_by?.username ?? "—"}
                </MetaItem>
                <MetaItem
                  label="Duration"
                  className={cn(run.status === "running" && "text-blue-500")}
                >
                  {run.status === "running" ? (
                    <TextDots>Running</TextDots>
                  ) : (
                    formatDuration(run.started_at, run.finished_at)
                  )}
                </MetaItem>
                <MetaItem label="Processed">
                  <span className="tabular-nums">
                    {run.total_processed.toLocaleString()}
                  </span>
                </MetaItem>
                <MetaItem label="Invalid" className="text-orange-500">
                  <span className="tabular-nums">
                    {run.total_invalid.toLocaleString()}
                  </span>
                </MetaItem>
                <MetaItem
                  label="Invalid rate"
                  className={cn(
                    run.total_invalid > 0 && "text-red-500",
                    run.total_invalid === 0 && "text-green-500"
                  )}
                >
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

          {run.status === "failed" &&
            run.error_message &&
            (isServerUnresponsiveError(run.error_message) ? (
              <Card className="border-amber-500/30 bg-amber-500/5">
                <CardContent className="flex items-start gap-3 py-4">
                  <WifiOff className="mt-0.5 h-5 w-5 text-amber-500" />
                  <div>
                    <p className="text-sm font-medium">
                      Server did not respond
                    </p>
                    <p className="text-xs text-muted-foreground">
                      The FHIR server stopped responding after several retries.
                      This is a server-side issue (the query took too long or
                      the connection was reset), not a problem with FHIR Verity.
                    </p>
                    <p className="mt-1 font-mono text-xs text-muted-foreground">
                      {run.error_message}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ) : (
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
            ))}
          <div className="flex items-center justify-between">
            <h2 className="mb-3 text-base font-medium">
              Invalid rate per resource type
            </h2>
            <div className="flex items-center gap-2">
              <Button onClick={() => setShowBar(!showBar)} variant="ghost">
                {showBar ? "Show as Radial Chart" : "Show as Bar Chart"}
                {showBar ? (
                  <PieChart2Icon className="ml-1 size-5" />
                ) : (
                  <CourseUpIcon className="ml-1 size-5" />
                )}
              </Button>
              <Button onClick={() => exportAsPNG()} size="sm" variant="ghost">
                Export the charts as PNG
                <ExportIcon className="ml-1 size-5" />
              </Button>
            </div>
          </div>
          <div ref={chartRef} className="space-y-6 py-4">
            {/* --- Bar chart: processed vs invalid per type ---------------- */}
            <Card className={cn(showBar ? "" : "hidden", "shadow-xs")}>
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
                  <div className="w-full">
                    <BarChart
                      data={run.per_resource_stats.map((s) => ({
                        type: s.resource_type,
                        processed: s.processed,
                        invalid: s.invalid,
                      }))}
                      barWidth={70}
                      className="max-h-96"
                      xDataKey="type"
                      margin={{ top: 8, right: 8, bottom: 40, left: 56 }}
                    >
                      <Grid horizontal />
                      <Bar
                        dataKey="processed"
                        fill="hsl(217 91% 60%)"
                        lineCap="round"
                      />
                      <Bar
                        dataKey="invalid"
                        fill="hsl(0 72% 51%)"
                        lineCap="round"
                      />
                      <ValueYAxis />
                      <BarXAxis />
                      <ChartTooltip />
                    </BarChart>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* --- Radial gauges: invalid rate per type -------------------- */}
            {run.per_resource_stats.length > 0 && (
              <div className={cn(!showBar ? "" : "hidden")}>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {run.per_resource_stats.map((s) => (
                    <RateGauge key={s.resource_type} stat={s} />
                  ))}
                </div>
              </div>
            )}
          </div>

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
                      <SortableTableHead
                        label="Resource type"
                        sortKey="resourceType"
                        activeKey={ruleSort.key}
                        dir={ruleSort.dir}
                        onSort={(key) =>
                          setRuleSort((prev) => nextSort(prev, key, "asc"))
                        }
                      />
                      <SortableTableHead
                        label="Rule"
                        sortKey="rule"
                        activeKey={ruleSort.key}
                        dir={ruleSort.dir}
                        onSort={(key) =>
                          setRuleSort((prev) => nextSort(prev, key, "asc"))
                        }
                      />
                      <SortableTableHead
                        label="Severity"
                        sortKey="severity"
                        activeKey={ruleSort.key}
                        dir={ruleSort.dir}
                        onSort={(key) =>
                          setRuleSort((prev) => nextSort(prev, key, "asc"))
                        }
                      />
                      <SortableTableHead
                        label="Count"
                        sortKey="count"
                        activeKey={ruleSort.key}
                        dir={ruleSort.dir}
                        onSort={(key) =>
                          setRuleSort((prev) => nextSort(prev, key, "desc"))
                        }
                        className="text-right"
                        align="right"
                      />
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
  className,
  children,
}: {
  label: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className={cn("text-sm", className)}>{children}</dd>
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
    <Card className="p-4 shadow-xs">
      <CardContent className="flex items-center gap-4 p-0">
        <div className="relative flex items-center justify-center">
          <ChartContainer config={gaugeConfig} className="h-23.75 w-23.75">
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
      <Skeleton className="h-85 w-full rounded-xl" />
    </div>
  )
}
