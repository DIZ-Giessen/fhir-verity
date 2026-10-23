import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft } from "lucide-react"

import {
  CalendarDateIcon,
  FilterCloseIcon,
} from "@solar-icons/react/line-duotone"
import { useEffect, useMemo, useState } from "react"
import { format, parse } from "date-fns"
import { de } from "date-fns/locale"
import type {
  ResourceConfig,
  ResourceFilters,
  RuleDefinition,
  RuleUpdate,
} from "@/api/queries"
import {
  configKeys,
  deleteServerConfig,
  patchRule,
  patchRules,
  serverQueryOptions,
  serverResourceConfigQueryOptions,
  updateServerFilters,
} from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { ApiError } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"

type Severity = "error" | "warning" | "info"

const CATEGORY_ORDER = [
  "privacy",
  "completeness",
  "coding",
  "plausibility",
  "integrity",
] as const

const CATEGORY_LABEL: Record<string, string> = {
  privacy: "Privacy & pseudonymization",
  completeness: "Structural completeness",
  coding: "Coding & terminology",
  plausibility: "Plausibility",
  integrity: "Referential integrity",
}

const CATEGORY_COLOR: Record<string, string> = {
  privacy: "text-rose-500",
  completeness: "text-orange-500",
  coding: "text-violet-500",
  plausibility: "text-blue-500",
  integrity: "text-teal-500",
}

type StateFilter = "all" | "enabled" | "disabled"

function matchesSearch(key: string, rule: RuleDefinition, search: string) {
  if (!search) return true
  const haystack =
    `${key} ${humanize(key)} ${rule.description ?? ""}`.toLowerCase()
  return search
    .toLowerCase()
    .split(/\s+/)
    .every((word) => haystack.includes(word))
}

const SEVERITY_TEXT: Record<Severity, string> = {
  error: "text-red-600 dark:text-red-400",
  warning: "text-amber-600 dark:text-amber-400",
  info: "text-sky-600 dark:text-sky-400",
}

function humanize(key: string) {
  const s = key.replace(/_/g, " ")
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export const Route = createFileRoute("/servers/$id/config/$resourceType")({
  component: ResourceConfigPage,
})

function ResourceConfigPage() {
  const { id, resourceType } = Route.useParams()
  const queryClient = useQueryClient()
  const queryKey = configKeys.resource(id, resourceType)

  const { data, isPending, error } = useQuery(
    serverResourceConfigQueryOptions(id, resourceType)
  )
  const serverQ = useQuery(serverQueryOptions(id))
  const serverName = serverQ.data?.name ?? id.slice(0, 8)
  const canWrite = serverQ.data?.can_write ?? false

  const patchMutation = useMutation({
    mutationFn: ({
      ruleKey,
      update,
    }: {
      ruleKey: string
      update: RuleUpdate
    }) => patchRule(id, resourceType, ruleKey, update),
    onMutate: async ({ ruleKey, update }) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<ResourceConfig>(queryKey)
      if (previous) {
        queryClient.setQueryData<ResourceConfig>(queryKey, {
          ...previous,
          is_server_specific: true,
          rules: {
            ...previous.rules,
            // RuleUpdate fields are nullable ("unchanged"); only apply set values
            [ruleKey]: {
              ...previous.rules[ruleKey],
              ...(Object.fromEntries(
                Object.entries(update).filter(([, v]) => v != null)
              ) as Partial<RuleDefinition>),
            },
          },
        })
      }
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(queryKey, ctx.previous)
    },
    onSuccess: (result) => {
      if (result) queryClient.setQueryData(queryKey, result)
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => deleteServerConfig(id, resourceType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  })

  const patch = (ruleKey: string, update: RuleUpdate) =>
    patchMutation.mutate({ ruleKey, update })

  const bulkMutation = useMutation({
    mutationFn: (rules: Record<string, RuleUpdate>) =>
      patchRules(id, resourceType, rules),
    onSuccess: (result) => {
      if (result) queryClient.setQueryData(queryKey, result)
    },
  })

  const setEnabled = (keys: Array<string>, enabled: boolean) =>
    bulkMutation.mutate(Object.fromEntries(keys.map((k) => [k, { enabled }])))

  const [search, setSearch] = useState("")
  const [stateFilter, setStateFilter] = useState<StateFilter>("all")

  const allRules = useMemo(() => Object.entries(data?.rules ?? {}), [data])
  const visibleRules = allRules.filter(
    ([key, rule]) =>
      matchesSearch(key, rule, search.trim()) &&
      (stateFilter === "all" ||
        (stateFilter === "enabled" ? rule.enabled : !rule.enabled))
  )
  const enabledCount = allRules.filter(([, rule]) => rule.enabled).length

  const filtersMutation = useMutation({
    mutationFn: (filters: ResourceFilters) =>
      updateServerFilters(id, resourceType, filters),
    onSuccess: (result) => {
      if (result) queryClient.setQueryData(queryKey, result)
    },
  })
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          to="/servers/$id/config"
          params={{ id }}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          All resource types
        </Link>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              {resourceType} rules for{" "}
              <span className="text-orange-500/70">{serverName}</span>
            </h1>
            {data?.is_server_specific ? (
              <Badge variant="destructive" className="mt-1.5">
                Server override
              </Badge>
            ) : (
              <Badge variant="secondary" className="mt-1.5">
                Defaults
              </Badge>
            )}
          </div>
          {data?.is_server_specific && canWrite && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
            >
              <FilterCloseIcon className="mr-2 size-5" />
              {resetMutation.isPending
                ? "Resetting..."
                : "Reset to default Configuration"}
            </Button>
          )}
        </div>
        <p className="mx-auto flex max-w-6xl text-sm text-muted-foreground">
          {canWrite
            ? "Toggle rules, change their severity, and edit regex patterns."
            : "Read only. Changing rules requires the editor role."}
        </p>
      </div>

      {data && (
        // A disabled fieldset makes every control inside read-only for viewers
        <fieldset disabled={!canWrite} className="m-0 min-w-0 border-0 p-0">
          <FilterCard
            initial={data.filters}
            onSave={(f) => filtersMutation.mutate(f)}
            saving={filtersMutation.isPending}
            error={filtersMutation.error}
          />
        </fieldset>
      )}
      {isPending && (
        <div className="space-y-2">
          {Array.from({ length: 14 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {error && (
        <div className="mx-auto max-w-6xl rounded-lg border p-8 text-center">
          <p className="text-sm font-medium text-destructive">
            {error instanceof ApiError && error.status === 404
              ? `'${resourceType}' is not a supported resource type`
              : "Failed to load configuration"}
          </p>
          {error instanceof ApiError && error.status !== 404 && (
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {`HTTP ${error.status} — ${error.statusText}`}
            </p>
          )}
        </div>
      )}

      {data && (
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search rules by name or description…"
            className="h-9 w-full sm:w-96"
          />
          <Select
            value={stateFilter}
            onValueChange={(value) => setStateFilter(value as StateFilter)}
          >
            <SelectTrigger className="h-9 w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All rules</SelectItem>
              <SelectItem value="enabled">Enabled only</SelectItem>
              <SelectItem value="disabled">Disabled only</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">
            {enabledCount} of {allRules.length} rules enabled
            {visibleRules.length !== allRules.length &&
              ` · ${visibleRules.length} shown`}
          </p>
        </div>
      )}

      {data && visibleRules.length === 0 && (
        <p className="mx-auto max-w-6xl py-6 text-center text-sm text-muted-foreground">
          No rules match the current search.
        </p>
      )}

      <fieldset
        disabled={!canWrite}
        className="m-0 min-w-0 space-y-6 border-0 p-0"
      >
        {data &&
          CATEGORY_ORDER.map((category) => {
            const entries = visibleRules.filter(
              ([, rule]) => rule.category === category
            )
            if (entries.length === 0) return null
            const keys = entries.map(([key]) => key)
            const allOn = entries.every(([, rule]) => rule.enabled)
            const allOff = entries.every(([, rule]) => !rule.enabled)

            return (
              <section
                key={category}
                className="mx-auto max-w-6xl space-y-2 rounded-xl border bg-sidebar-accent/20 px-1 pt-5"
              >
                <div className="flex items-center justify-between gap-2 px-4 py-2">
                  <h2
                    className={cn(
                      "text-xs font-medium tracking-wide capitalize",
                      CATEGORY_COLOR[category] ?? "text-muted-foreground"
                    )}
                  >
                    {CATEGORY_LABEL[category] ?? category}
                    <span className="ml-2 text-muted-foreground">
                      {entries.filter(([, rule]) => rule.enabled).length}/
                      {entries.length}
                    </span>
                  </h2>
                  {canWrite && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        disabled={allOn || bulkMutation.isPending}
                        onClick={() => setEnabled(keys, true)}
                      >
                        Enable all
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        disabled={allOff || bulkMutation.isPending}
                        onClick={() => setEnabled(keys, false)}
                      >
                        Disable all
                      </Button>
                    </div>
                  )}
                </div>
                <div className="divide-y overflow-hidden rounded-xl border bg-accent">
                  {entries.map(([key, rule]) => (
                    <div key={key} className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1">
                          <p className="font-medium">{humanize(key)}</p>
                          {rule.description && (
                            <p className="text-sm text-pretty text-muted-foreground">
                              {rule.description}
                            </p>
                          )}
                        </div>
                        <Switch
                          checked={rule.enabled}
                          onCheckedChange={(value) =>
                            patch(key, { enabled: value })
                          }
                          aria-label={`Enable ${humanize(key)}`}
                        />
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <Select
                          value={rule.severity}
                          onValueChange={(value) =>
                            patch(key, { severity: value as Severity })
                          }
                        >
                          <SelectTrigger
                            className={cn(
                              "h-8 w-32",
                              SEVERITY_TEXT[rule.severity]
                            )}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="error">Error</SelectItem>
                            <SelectItem value="warning">Warning</SelectItem>
                            <SelectItem value="info">Info</SelectItem>
                          </SelectContent>
                        </Select>

                        {rule.pattern != null && (
                          <Input
                            key={`${key}-${rule.pattern}`}
                            defaultValue={rule.pattern}
                            placeholder="Regex pattern"
                            spellCheck={false}
                            className="h-8 w-full max-w-xs font-mono text-xs"
                            onBlur={(e) => {
                              const next = e.target.value
                              if (next !== rule.pattern)
                                patch(key, { pattern: next })
                            }}
                          />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )
          })}
      </fieldset>
    </div>
  )
}

function FilterCard({
  initial,
  onSave,
  saving,
  error,
}: {
  initial: ResourceFilters
  onSave: (f: ResourceFilters) => void
  saving: boolean
  error: unknown
}) {
  const [from, setFrom] = useState<Date | undefined>(
    initial.last_updated_from ? parseYmd(initial.last_updated_from) : undefined
  )
  const [to, setTo] = useState<Date | undefined>(
    initial.last_updated_to ? parseYmd(initial.last_updated_to) : undefined
  )
  const [profile, setProfile] = useState(initial.profile ?? "")
  const [tag, setTag] = useState(initial.tag ?? "")

  // Re-sync when the query refetches (e.g. after reset-to-defaults)
  useEffect(() => {
    setFrom(
      initial.last_updated_from
        ? parseYmd(initial.last_updated_from)
        : undefined
    )
    setTo(
      initial.last_updated_to ? parseYmd(initial.last_updated_to) : undefined
    )
    setProfile(initial.profile ?? "")
    setTag(initial.tag ?? "")
  }, [initial])

  const active =
    (initial.last_updated_from ||
      initial.last_updated_to ||
      initial.profile ||
      initial.tag) != null &&
    Boolean(
      initial.last_updated_from ||
      initial.last_updated_to ||
      initial.profile ||
      initial.tag
    )

  const submit = () =>
    onSave({
      last_updated_from: from ? format(from, "yyyy-MM-dd") : null,
      last_updated_to: to ? format(to, "yyyy-MM-dd") : null,
      profile: profile || null,
      tag: tag || null,
    })

  const clear = () => {
    setFrom(undefined)
    setTo(undefined)
    setProfile("")
    setTag("")
    onSave({
      last_updated_from: null,
      last_updated_to: null,
      profile: null,
      tag: null,
    })
  }

  return (
    <section className="mx-auto max-w-6xl space-y-4 rounded-xl border bg-sidebar-accent/20 p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-orange-500">
            Scope filters.
          </h2>
          <p className="text-xs text-pretty text-muted-foreground">
            Restrict which resources are validated. Empty = validate everything.
          </p>
        </div>
        {active && <Badge variant="destructive">Filtered</Badge>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="text-xs">Last updated from</Label>
          <DateField value={from} onChange={setFrom} placeholder="Start date" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Last updated to</Label>
          <DateField value={to} onChange={setTo} placeholder="End date" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Profile</Label>
          <Input
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            spellCheck={false}
            placeholder="Your FHIR profile URL"
            className="h-8 font-mono text-xs"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Tag</Label>
          <Input
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder="system or code "
            spellCheck={false}
            className="h-8 font-mono text-xs"
          />
        </div>
      </div>

      {error instanceof ApiError && (
        <p className="text-xs text-destructive">
          {typeof error.body === "object" &&
          error.body &&
          "detail" in error.body
            ? String(error.body.detail)
            : `HTTP ${error.status}`}
        </p>
      )}

      <div className="flex items-center gap-2">
        <Button size="sm" onClick={submit} disabled={saving}>
          {saving ? "Saving..." : "Apply filters"}
        </Button>
        {active && (
          <Button size="sm" variant="outline" onClick={clear} disabled={saving}>
            Clear filters
          </Button>
        )}
      </div>
    </section>
  )
}

function parseYmd(s: string): Date | undefined {
  // Backend stores YYYY-MM-DD; guard against partial values (e.g. "2022").
  const d = parse(s, "yyyy-MM-dd", new Date())
  return isNaN(d.getTime()) ? undefined : d
}

function DateField({
  value,
  onChange,
  placeholder,
}: {
  value: Date | undefined
  onChange: (d: Date | undefined) => void
  placeholder: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          data-empty={!value}
          className="h-8 w-full justify-between text-left text-xs font-normal data-[empty=true]:text-muted-foreground"
        >
          {value ? (
            format(value, "PPP", { locale: de })
          ) : (
            <span>{placeholder}</span>
          )}
          <CalendarDateIcon className="size-4!" data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value}
          captionLayout="dropdown"
          onSelect={(d) => {
            onChange(d)
            setOpen(false)
          }}
          defaultMonth={value}
        />
      </PopoverContent>
    </Popover>
  )
}
