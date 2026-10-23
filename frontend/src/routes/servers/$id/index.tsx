import { useQueries, useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  KeyRound,
  Pencil,
  Play,
  Settings,
} from "lucide-react"
import { useState } from "react"

import {
  DangerCircleIcon,
  DangerTriangleIcon,
  ExpressionlessSquareIcon,
  RefreshIcon,
} from "@solar-icons/react/line-duotone"
import { formatDistanceStrict, formatDistanceToNow } from "date-fns"
import type {
  ResourceCount,
  ServerMetadata,
  ValidationRunListItem,
} from "@/api/queries"
import {
  runSummaryQueryOptions,
  serverMetadataQueryOptions,
  serverQueryOptions,
  serverResourceConfigQueryOptions,
  serverResourceCountsQueryOptions,
  serverRunsQueryOptions,
} from "@/api/queries"
import { ServerAuthDialog } from "@/components/server-auth-dialog"
import { ServerFormDialog } from "@/components/server-form-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ApiError } from "@/lib/api-client"
import { filterEntries, hasActiveFilters } from "@/lib/filter-format"
import { cn } from "@/lib/utils"
import { StartValidationDialog } from "@/components/start-validation-dialog"
import { Dots } from "@/components/dots"
import { TextDots } from "@/components/text-dots"

export const Route = createFileRoute("/servers/$id/")({
  component: ServerDetailPage,
})

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

function formatDuration(startISO: string, endISO: string | null): string {
  if (!endISO) return "—"
  const sec = Math.round(
    (new Date(endISO).getTime() - new Date(startISO).getTime()) / 1000
  )
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return `${m}m ${s}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

function ServerDetailPage() {
  const { id } = Route.useParams()

  const serverQ = useQuery(serverQueryOptions(id))
  const runsQ = useQuery(serverRunsQueryOptions(id, 5))
  const countsQ = useQuery(serverResourceCountsQueryOptions(id))
  const metaQ = useQuery({
    ...serverMetadataQueryOptions(id),
    enabled: false,
  })

  // One config lookup per resource type shown in the counts table, so an
  // active *filter* (lastUpdate/profile/tag — not validation rules) can be
  // flagged next to the resource. Prevents mistaking a filtered count for
  // the server's full count, or mixing it up with another resource type.
  const resourceTypes = countsQ.data?.map((c) => c.resource_type) ?? []
  const configQs = useQueries({
    queries: resourceTypes.map((rt) => ({
      ...serverResourceConfigQueryOptions(id, rt),
      enabled: Boolean(countsQ.data),
    })),
  })
  const filterMap = new Map<string, Record<string, unknown>>()
  configQs.forEach((q, i) => {
    const filters = q.data?.filters
    if (hasActiveFilters(filters)) {
      filterMap.set(resourceTypes[i], filters)
    }
  })

  const latestCompleted = runsQ.data?.items.find(
    (r) => r.status === "completed"
  )
  const summaryQ = useQuery({
    ...runSummaryQueryOptions(latestCompleted?.id ?? ""),
    enabled: Boolean(latestCompleted),
  })

  const [editOpen, setEditOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [startOpen, setStartOpen] = useState(false)

  if (serverQ.isPending) {
    return <Skeleton className="h-96 w-full" />
  }

  if (serverQ.error || !serverQ.data) {
    return (
      <div className="rounded-lg border p-8 text-center">
        <p className="text-sm font-medium text-destructive">
          Failed to load server
        </p>
        <p className="mt-1 font-mono text-xs text-muted-foreground">
          {serverQ.error instanceof ApiError
            ? `HTTP ${serverQ.error.status} — ${serverQ.error.statusText}`
            : serverQ.error?.message}
        </p>
      </div>
    )
  }

  const server = serverQ.data

  return (
    <div className="space-y-6">
      <Link
        to="/servers"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="mr-1 h-4 w-4" />
        Back to servers
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {server.name}
          </h1>
          <p className="font-mono text-xs text-muted-foreground">
            {server.base_url}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {server.can_write && (
            <Button onClick={() => setStartOpen(true)}>
              <Play className="mr-2 size-4" />
              Start validation
            </Button>
          )}
          {server.can_manage && (
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
          )}
          <Button variant="outline" asChild>
            <Link to="/servers/$id/config" params={{ id }}>
              <Settings className="mr-2 h-4 w-4" />
              Config
            </Link>
          </Button>
          {server.can_manage && (
            <Button variant="outline" onClick={() => setAuthOpen(true)}>
              <KeyRound className="mr-2 h-4 w-4" />
              Server auth
            </Button>
          )}
        </div>
      </div>

      {/* KPI cards from latest completed run */}
      <KpiRow run={latestCompleted ?? null} />

      {/* Severity breakdown from latest completed run */}
      <SeverityRow
        summary={summaryQ.data ?? null}
        loading={summaryQ.isFetching}
        hasRun={Boolean(latestCompleted)}
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <ConnectionTestCard
          data={metaQ.data}
          loading={metaQ.isFetching}
          onTest={() => metaQ.refetch()}
        />
        <ResourceCountsCard
          counts={countsQ.data ?? []}
          loading={countsQ.isPending}
          onRefresh={() => countsQ.refetch()}
          filterMap={filterMap}
        />
      </div>

      <RecentRunsCard
        runs={runsQ.data?.items ?? []}
        loading={runsQ.isPending}
      />

      <ServerFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        server={server}
      />
      <ServerAuthDialog
        open={authOpen}
        onOpenChange={setAuthOpen}
        server={server}
      />
      <StartValidationDialog
        open={startOpen}
        onOpenChange={setStartOpen}
        serverId={server.id}
        serverName={server.name}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/* const AUTH_LABELS: Record<string, string> = {
  none: "No auth",
  basic: "Basic auth",
  oauth2_client_credentials: "OAuth2",
}

const AUTH_STYLES: Record<string, string> = {
  none: "border-0 bg-zinc-500/15 text-zinc-700 dark:bg-zinc-500/10 dark:text-zinc-400",
  basic:
    "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
  oauth2_client_credentials:
    "border-0 bg-violet-500/15 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400",
} */

/* function AuthBadge({ type }: { type: string }) {
  return (
    <Badge variant="outline" className={AUTH_STYLES[type] ?? ""}>
      {AUTH_LABELS[type] ?? type}
    </Badge>
  )
} */

function KpiRow({ run }: { run: ValidationRunListItem | null }) {
  const rate =
    run && run.total_processed > 0
      ? (run.total_invalid / run.total_processed) * 100
      : null
  /* dateFormatter.format(new Date(run.started_at))  */
  /* relativeTime(run.started_at)  */
  const cards: Array<{ name: string; stat: string; sub?: string }> = [
    {
      name: "Last successful validation",

      stat: run ? formatDistanceToNow(run.started_at) : "—",
      sub: run
        ? formatDistanceStrict(run.started_at, new Date())
        : "No runs yet",
    },
    {
      name: "Processed",
      stat: run ? run.total_processed.toLocaleString() : "—",
    },
    {
      name: "Invalid",
      stat: run ? run.total_invalid.toLocaleString() : "—",
    },
    {
      name: "Invalid rate",
      stat: rate != null ? `${rate.toFixed(1)}%` : "—",
    },
  ]

  return (
    <dl className="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((item) => (
        <Card
          key={item.name}
          className="rounded-none border-l! p-6 py-4 shadow-none ring-0 first:border-none"
        >
          <CardContent className="items-center p-4">
            <dt
              className={cn(
                "text-sm font-medium text-muted-foreground"
                /*  item.name === "Invalid"
                  ? "text-rose-500"
                  : item.name === "Invalid rate" && "text-orange-500" */
              )}
            >
              {item.name}
            </dt>
            <dd className="mt-2 flex items-baseline space-x-2.5">
              <span
                className={cn(
                  "text-foregroundtabular-nums text-3xl font-semibold",
                  item.name === "Invalid"
                    ? "text-red-600"
                    : item.name === "Invalid rate" && "text-orange-600"
                )}
              >
                {item.stat}
              </span>
            </dd>
            {/*   {item.sub && (
              <p className="mt-1 text-xs text-muted-foreground">{item.sub}</p>
            )} */}
          </CardContent>
        </Card>
      ))}
    </dl>
  )
}

interface SeverityRowProps {
  summary: {
    by_resource_type: Array<{
      by_rule: Array<{ severity: string; count: number }>
      resource_type: string
    }>
  } | null
  loading: boolean
  hasRun: boolean
}

function SeverityRow({ summary, loading, hasRun }: SeverityRowProps) {
  const counts = { error: 0, warning: 0, info: 0 }
  summary?.by_resource_type.forEach((rt) => {
    rt.by_rule.forEach((r) => {
      if (r.severity in counts) {
        counts[r.severity as keyof typeof counts] += r.count
      }
    })
  })

  const items = [
    {
      key: "error",
      name: "Errors",
      stat: counts.error,
      Icon: DangerTriangleIcon,
      tone: "text-red-500",
      description: "Critical issues that block successful validation.",

      label: "Errors",
    },
    {
      key: "warning",
      name: "Warnings",
      stat: counts.warning,
      Icon: DangerTriangleIcon,
      tone: "text-orange-500",
      description: "Should be resolved to improve validation quality.",

      label: "Warnings",
    },
    {
      key: "info",
      name: "Infos",
      stat: counts.info,
      Icon: DangerCircleIcon,
      tone: "text-blue-500",
      description: "Non-critical information.",

      label: "Infos",
    },
  ]

  if (!hasRun) {
    return (
      <Card className="p-6 shadow-2xs">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <ExpressionlessSquareIcon className="size-5.5" />
          No completed validation runs yet. Start one to see issue counts.
        </p>
      </Card>
    )
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    )
  }

  return (
    <dl className="grid grid-cols-1 gap-6 sm:grid-cols-3">
      <span className="col-span-3 text-sm text-muted-foreground">
        across resource{summary?.by_resource_type.length === 1 ? "" : "s"}{" "}
        {summary?.by_resource_type.map((i) => i.resource_type).join(", ")}
      </span>
      {items.map((item) => (
        <Card key={item.key} className="! p-6 shadow">
          <CardContent className="p-0">
            <dt className="text-sm font-medium text-muted-foreground">
              {item.name}
            </dt>
            <dd className="text-3xl font-semibold text-foreground tabular-nums">
              {item.stat.toLocaleString()}
            </dd>
            <div className="mt-4 flex items-center gap-3 rounded-xl bg-muted/50 p-2">
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded",
                  item.tone
                )}
              >
                <item.Icon className="size-7" />
              </span>
              <p className="text-sm text-muted-foreground">
                {item.description}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </dl>
  )
}

interface ConnectionTestCardProps {
  data?: ServerMetadata | null
  loading: boolean
  onTest: () => void
}

function ConnectionTestCard({
  data,
  loading,
  onTest,
}: ConnectionTestCardProps) {
  return (
    <Card className="col-span-2 shadow-2xs">
      <CardHeader>
        <CardTitle className="text-base">Connection test</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={onTest} disabled={loading}>
          {loading ? <TextDots>Loading</TextDots> : "Test connection"}
        </Button>

        {data && data.ok && (
          <dl className="space-y-2 text-sm">
            <Row label="Status">
              <Badge
                variant="outline"
                className="border-0 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
              >
                Reachable
              </Badge>
            </Row>
            <Row label="Response time">{data.response_ms} ms</Row>
            <Row label="FHIR version">{data.fhir_version ?? "—"}</Row>
            <Row label="Software">
              {data.software_name
                ? `${data.software_name}${data.software_version ? ` ${data.software_version}` : ""}`
                : "—"}
            </Row>
          </dl>
        )}

        {data && !data.ok && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
            <p className="text-sm font-medium text-destructive">
              Connection failed
            </p>
            <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
              {data.error ?? "Unknown error"}
            </p>
          </div>
        )}

        {!data && !loading && (
          <p className="text-sm text-muted-foreground">
            Test the FHIR server reachability and read its CapabilityStatement.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  )
}

function FilterBadge({ filters }: { filters: Record<string, unknown> }) {
  const entries = filterEntries(filters)
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="gap-1 border-0 bg-amber-500/15 px-1.5 py-0 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"
        >
          <Filter className="size-3" />
          filtered
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-none">
        <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5">
          {entries.map((e) => (
            <div key={e.label} className="contents">
              <dt className="text-background/60">{e.label}</dt>
              <dd className="font-medium">{e.value}</dd>
            </div>
          ))}
        </dl>
      </TooltipContent>
    </Tooltip>
  )
}

interface ResourceCountsCardProps {
  counts: Array<ResourceCount>
  loading: boolean
  onRefresh: () => void
  filterMap: Map<string, Record<string, unknown>>
}

function ResourceCountsCard({
  counts,
  loading,
  onRefresh,
  filterMap,
}: ResourceCountsCardProps) {
  return (
    <Card className="col-span-3 shadow-2xs">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Resource counts</CardTitle>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onRefresh}
          disabled={loading}
          aria-label="Refresh counts"
        >
          {loading ? (
            <Dots className="w-5" />
          ) : (
            <RefreshIcon className="size-5" />
          )}
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex w-full items-center justify-center space-y-2">
            <TextDots className="text-muted-foreground [--delay:280ms] [--duration:2s]">
              Fetching data
            </TextDots>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource type</TableHead>
                <TableHead className="text-right">Count</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {counts.map((c) => {
                const filters = filterMap.get(c.resource_type)
                return (
                  <TableRow key={c.resource_type}>
                    <TableCell className="font-medium">
                      <span className="inline-flex items-center gap-1.5">
                        {c.resource_type}
                        {filters && <FilterBadge filters={filters} />}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {c.ok ? (
                        c.total.toLocaleString()
                      ) : (
                        <span
                          title={c.error ?? "Unknown error"}
                          className="text-destructive"
                        >
                          error
                        </span>
                      )}
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

const RUN_STATUS_STYLES: Record<string, string> = {
  completed:
    "border-0 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
  running:
    "border-0 bg-blue-500/15 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400",
  failed:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  cancelled:
    "border-0 bg-neutral-500/15 text-neutral-700 dark:bg-neutral-500/10 dark:text-neutral-400",
}

function RecentRunsCard({
  runs,
  loading,
}: {
  runs: Array<ValidationRunListItem>
  loading: boolean
}) {
  return (
    <Card className="shadow-2xs">
      <CardHeader>
        <CardTitle className="text-base">Recent validation runs</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
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
                <TableHead>Started by</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">Processed</TableHead>
                <TableHead className="text-right">Invalid</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((r) => (
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
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDuration(r.started_at, r.finished_at)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.total_processed.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.total_invalid.toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Link to="/runs/$runId" params={{ runId: r.id }}>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
