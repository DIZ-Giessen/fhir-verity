import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { AlertTriangle, CheckCircle2, ChevronLeft } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { runQueryOptions } from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { env } from "@/lib/env"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/runs/$runId_/live")({
  component: LivePage,
})

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type WsMessage = { type?: string } & Record<string, unknown>

interface LiveMetrics {
  totalProcessed: number
  totalInvalid: number
  rps: number | null
  elapsedSeconds: number | null
  currentResource: string | null
  pagesDone: number | null
  progressPercent: number | null
  etaSeconds: number | null
}

interface LogEntry {
  id: number
  time: string
  type: string
  msg: string
}

type ConnState = "connecting" | "connected" | "disconnected" | "error"

const nf = new Intl.NumberFormat()
const num = (v: unknown) => (typeof v === "number" ? v : null)
const str = (v: unknown) => (typeof v === "string" ? v : null)
const fmt = (n: number | null) => (n == null ? "—" : nf.format(n))
function fmtTime(s: number): string {
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

const CONN_META: Record<
  ConnState,
  { dot: string; label: string; cls: string }
> = {
  connecting: {
    dot: "bg-amber-500",
    label: "Connecting…",
    cls: "text-amber-600 dark:text-amber-400",
  },
  connected: {
    dot: "bg-emerald-500 animate-pulse",
    label: "Connected",
    cls: "text-emerald-600 dark:text-emerald-400",
  },
  disconnected: {
    dot: "bg-muted-foreground",
    label: "Disconnected",
    cls: "text-muted-foreground",
  },
  error: {
    dot: "bg-red-500",
    label: "Connection error",
    cls: "text-red-600 dark:text-red-400",
  },
}

const LOG_TYPE_STYLES: Record<string, string> = {
  progress: "text-primary",
  completed: "text-emerald-500",
  failed: "text-red-500",
  resource_start: "text-amber-500",
  system: "text-muted-foreground",
  raw: "text-muted-foreground",
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function LivePage() {
  const { runId } = Route.useParams()
  const queryClient = useQueryClient()
  const runQ = useQuery(runQueryOptions(runId))

  const [conn, setConn] = useState<ConnState>("connecting")
  const [runState, setRunState] = useState<string>("running")
  const [metrics, setMetrics] = useState<LiveMetrics>({
    totalProcessed: 0,
    totalInvalid: 0,
    rps: null,
    elapsedSeconds: null,
    currentResource: null,
    pagesDone: null,
    progressPercent: null,
    etaSeconds: null,
  })
  const [log, setLog] = useState<LogEntry[]>([])

  const logIdRef = useRef(0)
  const terminalRef = useRef(false)
  const seededRef = useRef(false)
  const logEndRef = useRef<HTMLDivElement>(null)

  const wsUrl = useMemo(
    () => `${env.API_URL.replace(/^http/, "ws")}/api/v1/ws/validation/${runId}`,
    [runId]
  )

  // Seed once from the run detail so an already-finished run shows final numbers
  useEffect(() => {
    if (!runQ.data || seededRef.current) return
    seededRef.current = true
    const d = runQ.data
    setRunState(d.status)
    if (d.status === "completed" || d.status === "failed")
      terminalRef.current = true
    setMetrics((m) => ({
      ...m,
      totalProcessed: d.total_processed,
      totalInvalid: d.total_invalid,
      elapsedSeconds: d.elapsed_seconds ?? null,
      progressPercent: d.status === "completed" ? 100 : m.progressPercent,
    }))
  }, [runQ.data])

  // auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [log])

  // WebSocket lifecycle
  useEffect(() => {
    let ws: WebSocket | null = null
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let closedByUs = false

    const pushLog = (type: string, msg: string) =>
      setLog((prev) => {
        const next = [
          ...prev,
          {
            id: logIdRef.current++,
            time: new Date().toLocaleTimeString(),
            type,
            msg,
          },
        ]
        return next.length > 200 ? next.slice(-200) : next
      })

    const handle = (data: WsMessage) => {
      switch (data.type) {
        case "progress":
          setMetrics({
            totalProcessed: num(data.total_processed) ?? 0,
            totalInvalid: num(data.total_invalid) ?? 0,
            rps: num(data.resources_per_second),
            elapsedSeconds: num(data.elapsed_seconds),
            currentResource: str(data.resource_type),
            pagesDone: num(data.pages_done),
            progressPercent: num(data.progress_percent),
            etaSeconds: num(data.eta_seconds),
          })
          pushLog(
            "progress",
            `${str(data.resource_type) ?? "?"} — ${fmt(
              num(data.total_processed)
            )} processed / ${fmt(num(data.total_invalid))} invalid — ${
              num(data.progress_percent) ?? "?"
            }% — ETA ${
              num(data.eta_seconds) != null
                ? fmtTime(num(data.eta_seconds)!)
                : "unknown"
            }`
          )
          break
        case "resource_start":
          setMetrics((m) => ({
            ...m,
            currentResource: str(data.resource_type),
            progressPercent: 0,
          }))
          pushLog("resource_start", `Started ${str(data.resource_type) ?? "?"}`)
          break
        case "completed":
          terminalRef.current = true
          setRunState("completed")
          setMetrics((m) => ({
            ...m,
            totalProcessed: num(data.total_processed) ?? m.totalProcessed,
            totalInvalid: num(data.total_invalid) ?? m.totalInvalid,
            progressPercent: 100,
          }))
          pushLog(
            "completed",
            `Completed — ${fmt(num(data.total_processed))} processed / ${fmt(
              num(data.total_invalid)
            )} invalid`
          )
          queryClient.invalidateQueries({
            queryKey: ["validation", "runs", runId],
          })
          break
        case "failed":
          terminalRef.current = true
          setRunState("failed")
          pushLog("failed", `Error: ${str(data.error) ?? "unknown"}`)
          break
        case "pong":
          break
        default:
          pushLog("raw", JSON.stringify(data))
      }
    }

    const open = () => {
      setConn("connecting")
      ws = new WebSocket(wsUrl)
      ws.onopen = () => {
        setConn("connected")
        pushLog("system", "Connected")
        ws?.send("ping")
        pingTimer = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) ws.send("ping")
        }, 25_000)
      }
      ws.onmessage = (e) => {
        try {
          handle(JSON.parse(e.data) as WsMessage)
        } catch {
          /* ignore non-JSON frames */
        }
      }
      ws.onerror = () => setConn("error")
      ws.onclose = () => {
        if (pingTimer) clearInterval(pingTimer)
        setConn("disconnected")
        if (!closedByUs && !terminalRef.current) {
          pushLog("system", "Reconnecting…")
          reconnectTimer = setTimeout(open, 2000)
        }
      }
    }

    open()
    return () => {
      closedByUs = true
      if (pingTimer) clearInterval(pingTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, wsUrl])

  const pct = metrics.progressPercent ?? (runState === "completed" ? 100 : 0)
  const c = CONN_META[conn]

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

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Live monitor
          </h1>
          <p className="font-mono text-xs text-muted-foreground">
            for run with ID {runId}
          </p>
        </div>
        <span className="flex items-center gap-2 text-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${c.dot}`} />
          <span className={c.cls}>{c.label}</span>
        </span>
      </div>

      {runState === "completed" && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            <p className="text-sm font-medium">
              This run has finished — showing final results.
            </p>
          </CardContent>
        </Card>
      )}
      {runState === "failed" && (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <p className="text-sm font-medium">This run failed.</p>
          </CardContent>
        </Card>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiTile label="Processed" value={fmt(metrics.totalProcessed)} accent />
        <KpiTile label="Invalid" value={fmt(metrics.totalInvalid)} />
        <KpiTile
          label="Resources / s"
          value={metrics.rps != null ? fmt(metrics.rps) : "—"}
        />
        <KpiTile
          label="Elapsed"
          value={
            metrics.elapsedSeconds != null
              ? fmtTime(metrics.elapsedSeconds)
              : "—"
          }
        />
      </div>

      {/* Progress */}
      <Card className="shadow-2xs">
        <CardContent className="space-y-3 py-5">
          <div className="flex items-center justify-between">
            <Badge variant="outline">{metrics.currentResource ?? "—"}</Badge>
            <span className="text-sm text-muted-foreground tabular-nums">
              {metrics.progressPercent != null
                ? `${metrics.progressPercent}%`
                : "—"}
            </span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-500",
                runState === "running"
                  ? "bg-primary"
                  : runState === "failed"
                    ? "bg-red-500"
                    : "bg-emerald-500"
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex gap-5 text-xs text-muted-foreground">
            <span>
              Pages:{" "}
              <span className="text-foreground">
                {metrics.pagesDone ?? "—"}
              </span>
            </span>
            <span>
              ETA:{" "}
              <span className="pl-1.5 text-foreground">
                {metrics.etaSeconds != null
                  ? fmtTime(metrics.etaSeconds)
                  : "finished"}
              </span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Event log */}
      <Card className="shadow-2xs">
        <CardHeader>
          <CardTitle className="text-base">Event log</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-72 overflow-y-auto rounded-md border bg-muted/20 p-3 font-mono text-xs">
            {log.length === 0 ? (
              <p className="text-muted-foreground">Waiting for events…</p>
            ) : (
              log.map((e) => (
                <div
                  key={e.id}
                  className="flex gap-3 border-b border-border/40 py-1 last:border-0"
                >
                  <span className="w-20 shrink-0 text-muted-foreground">
                    {e.time}
                  </span>
                  <span
                    className={`w-28 shrink-0 font-semibold ${
                      LOG_TYPE_STYLES[e.type] ?? "text-muted-foreground"
                    }`}
                  >
                    {e.type}
                  </span>
                  <span className="break-all">{e.msg}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </CardContent>
      </Card>

      {runState === "completed" && (
        <div className="flex justify-end">
          <Button asChild>
            <Link to="/runs/$runId/invalid-resources" params={{ runId }}>
              View invalid resources
            </Link>
          </Button>
        </div>
      )}
    </div>
  )
}

function KpiTile({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <Card className="shadow-2xs">
      <CardContent className="py-5">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </p>
        <p
          className={`mt-1 text-2xl font-semibold tabular-nums ${
            accent ? "text-primary" : ""
          }`}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  )
}
