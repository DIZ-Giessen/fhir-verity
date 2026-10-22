import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react"
import { Fragment, useEffect, useMemo, useState } from "react"

import type { AuditLogParams } from "@/api/queries"
import {
  auditLogDetailQueryOptions,
  auditLogQueryOptions,
  resourceTypesQueryOptions,
  serversQueryOptions,
  usersQueryOptions,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { dateFormatter } from "@/lib/functions/runs"

export const Route = createFileRoute("/audit")({ component: AuditPage })

const PAGE_SIZE = 50
const ALL = "all"

const ACTION_LABELS: Record<string, string> = {
  DELETE: "Delete",
  PATCH: "Patch",
  BULK_DELETE: "Bulk delete",
  BULK_PATCH: "Bulk fix",
  SERVER_DELETE: "Server deleted",
}

/** Summary rows written by bulk-delete/-fix (one row per operation). */
const SUMMARY_ACTIONS = new Set(["BULK_DELETE", "BULK_PATCH"])

/** Rows about Verity itself, not about a resource on the FHIR server. */
const SERVER_ACTIONS = new Set(["SERVER_DELETE"])

interface BulkPayload {
  bulk: true
  filter?: Record<string, string | null>
  matched?: number
  succeeded?: number
  failed?: number
  elapsed_seconds?: number
  succeeded_resources?: Array<string>
  failed_by_error?: Record<string, Array<string>>
}

function isBulkPayload(value: unknown): value is BulkPayload {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { bulk?: unknown }).bulk === true
  )
}

const STATUS_STYLES: Record<string, string> = {
  success:
    "border-0 bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
  failed:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
}

function AuditPage() {
  const [page, setPage] = useState(0)
  const [serverId, setServerId] = useState(ALL)
  const [resourceType, setResourceType] = useState(ALL)
  const [action, setAction] = useState(ALL)
  const [status, setStatus] = useState(ALL)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    setPage(0)
  }, [serverId, resourceType, action, status])

  const params: AuditLogParams = {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    server_id: serverId === ALL ? undefined : serverId,
    resource_type: resourceType === ALL ? undefined : resourceType,
    // Select values come from the AuditAction/AuditStatus option lists below.
    action: action === ALL ? undefined : (action as AuditLogParams["action"]),
    status_filter:
      status === ALL ? undefined : (status as AuditLogParams["status_filter"]),
  }

  const listQ = useQuery(auditLogQueryOptions(params))
  const serversQ = useQuery(serversQueryOptions())
  const typesQ = useQuery(resourceTypesQueryOptions())

  const usersQ = useQuery(usersQueryOptions())

  const actorName = useMemo(() => {
    const m = new Map(
      (usersQ.data ?? []).map((u) => [u.id, u.username || u.email || u.id])
    )
    return (id: string | null | undefined) =>
      id ? (m.get(id) ?? id) : "System"
  }, [usersQ.data])

  const serverName = useMemo(() => {
    const m = new Map((serversQ.data ?? []).map((s) => [s.id, s.name]))
    return (id: string | null | undefined, baseUrl: string) =>
      (id && m.get(id)) ?? baseUrl
  }, [serversQ.data])

  const items = listQ.data?.items ?? []
  const total = listQ.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters =
    serverId !== ALL || resourceType !== ALL || action !== ALL || status !== ALL

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every delete and patch executed against a FHIR server, and every
          deleted server. Bulk operations are logged as a single summary entry.
        </p>
      </div>

      <Card className="shadow-2xs">
        <CardHeader className="gap-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Actions</CardTitle>
            <p className="text-xs text-muted-foreground">
              {total.toLocaleString()} total
            </p>
          </div>
          <div className="grid w-full flex-wrap items-center gap-2 sm:grid-cols-4">
            <Select value={serverId} onValueChange={setServerId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Server" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All servers</SelectItem>
                {(serversQ.data ?? []).map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={resourceType} onValueChange={setResourceType}>
              <SelectTrigger className="w-full">
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

            <Select value={action} onValueChange={setAction}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All actions</SelectItem>
                {Object.entries(ACTION_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>

            {hasFilters && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setServerId(ALL)
                  setResourceType(ALL)
                  setAction(ALL)
                  setStatus(ALL)
                }}
              >
                Reset
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent>
          {listQ.isPending ? (
            <div className="space-y-2">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No audit entries match the current filters.
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
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Resource</TableHead>
                    <TableHead>Server</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>User</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((a) => {
                    const isOpen = expanded.has(a.id)
                    const st = a.status.toLowerCase()
                    return (
                      <Fragment key={a.id}>
                        <TableRow
                          className="cursor-pointer"
                          onClick={() => toggle(a.id)}
                        >
                          <TableCell>
                            <ChevronDown
                              className={`h-4 w-4 text-muted-foreground transition-transform ${
                                isOpen ? "" : "-rotate-90"
                              }`}
                            />
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {dateFormatter.format(new Date(a.executed_at))}
                          </TableCell>
                          <TableCell className="font-medium">
                            {ACTION_LABELS[a.action] ?? a.action}
                          </TableCell>
                          <TableCell>
                            <span className="font-mono text-xs">
                              {SUMMARY_ACTIONS.has(a.action)
                                ? `${a.resource_type === "*" ? "All types" : a.resource_type} · ${a.resource_id}`
                                : SERVER_ACTIONS.has(a.action)
                                  ? a.resource_id
                                  : `${a.resource_type}/${a.resource_id}`}
                            </span>
                          </TableCell>
                          <TableCell className="text-xs">
                            {serverName(a.server_id, a.server_base_url)}
                          </TableCell>

                          <TableCell>
                            <Badge
                              variant="outline"
                              className={STATUS_STYLES[st] ?? ""}
                            >
                              {a.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">
                            {actorName(a.actor_id)}
                          </TableCell>
                        </TableRow>

                        {isOpen && (
                          <TableRow key={`${a.id}-detail`}>
                            <TableCell colSpan={7} className="bg-muted/30 p-0">
                              <AuditDetail auditId={a.id} />
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

function AuditDetail({ auditId }: { auditId: string }) {
  const q = useQuery(auditLogDetailQueryOptions(auditId))

  if (q.isPending) {
    return (
      <div className="space-y-2 px-4 py-4">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }
  if (!q.data) {
    return (
      <p className="px-4 py-4 text-sm text-muted-foreground">
        Could not load detail.
      </p>
    )
  }

  const d = q.data
  const fhirUrl = `${d.server_base_url.replace(/\/$/, "")}/${d.resource_type}/${d.resource_id}`
  const isSummary = SUMMARY_ACTIONS.has(d.action)
  const isServerAction = SERVER_ACTIONS.has(d.action)
  const bulk = isBulkPayload(d.fhir_request_payload)
    ? d.fhir_request_payload
    : null

  return (
    <div className="space-y-4 px-4 py-4">
      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <Field label="FHIR response">{d.fhir_response_status ?? "—"}</Field>
        <Field label="Reason">{d.reason ?? "—"}</Field>
        {d.error_message && (
          <div className="text-wrap sm:col-span-2">
            <Field label="Error">
              <span className="text-red-600 dark:text-red-400">
                {d.error_message}
              </span>
            </Field>
          </div>
        )}
      </div>

      {bulk ? (
        <BulkSummary payload={bulk} />
      ) : (
        d.fhir_request_payload != null && (
          <JsonBlock
            label={isSummary ? "Operation" : "Patch payload"}
            value={d.fhir_request_payload}
          />
        )
      )}
      {d.resource_before != null && (
        <JsonBlock
          label={isServerAction ? "Server before deletion" : "Resource before"}
          value={d.resource_before}
        />
      )}

      {!isSummary && !isServerAction && (
        <Button asChild size="sm" variant="outline" className="gap-1">
          <a href={fhirUrl} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5" />
            Open on FHIR server
          </a>
        </Button>
      )}
    </div>
  )
}

function BulkSummary({ payload }: { payload: BulkPayload }) {
  const failedGroups = Object.entries(payload.failed_by_error ?? {})
  const filter = Object.entries(payload.filter ?? {}).filter(
    ([, v]) => v != null
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">Matched: {payload.matched ?? 0}</Badge>
        <Badge variant="outline" className={STATUS_STYLES.success}>
          Succeeded: {payload.succeeded ?? 0}
        </Badge>
        {(payload.failed ?? 0) > 0 && (
          <Badge variant="outline" className={STATUS_STYLES.failed}>
            Failed: {payload.failed}
          </Badge>
        )}
        {payload.elapsed_seconds != null && (
          <Badge variant="outline">{payload.elapsed_seconds}s</Badge>
        )}
      </div>

      {filter.length > 0 && (
        <Field label="Filter">
          <span className="font-mono text-xs">
            {filter.map(([k, v]) => `${k}=${v}`).join(" · ")}
          </span>
        </Field>
      )}

      {failedGroups.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Failures by error
          </p>
          <ul className="space-y-2">
            {failedGroups.map(([error, refs]) => (
              <li key={error} className="rounded-lg border bg-background p-2">
                <p className="text-xs text-red-600 dark:text-red-400">
                  {error}{" "}
                  <span className="text-muted-foreground">({refs.length})</span>
                </p>
                <ResourceList refs={refs} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {(payload.succeeded_resources?.length ?? 0) > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Changed resources ({payload.succeeded_resources?.length})
          </p>
          <div className="rounded-lg border bg-background p-2">
            <ResourceList refs={payload.succeeded_resources ?? []} />
          </div>
        </div>
      )}
    </div>
  )
}

const RESOURCE_PREVIEW = 200

function ResourceList({ refs }: { refs: Array<string> }) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? refs : refs.slice(0, RESOURCE_PREVIEW)
  return (
    <div className="mt-1 max-h-48 overflow-auto">
      <p className="font-mono text-xs break-all text-muted-foreground">
        {visible.join(", ")}
      </p>
      {refs.length > RESOURCE_PREVIEW && (
        <Button
          variant="link"
          size="sm"
          className="h-auto p-0 text-xs"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll
            ? "Show less"
            : `Show all ${refs.length.toLocaleString()} resources`}
        </Button>
      )}
    </div>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div>
      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </p>
      <p className="wrap-break-word">{children}</p>
    </div>
  )
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </p>
      <pre className="max-h-72 overflow-auto rounded-lg border bg-background p-3 font-mono text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}
