import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft } from "lucide-react"

import {
  type ResourceConfig,
  type RuleUpdate,
  configKeys,
  deleteServerConfig,
  patchRule,
  serverResourceConfigQueryOptions,
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
import { Restart } from "@solar-icons/react-perf/category/style/LineDuotone"

type Severity = "error" | "warning" | "info"

const CATEGORY_ORDER = [
  "privacy",
  "completeness",
  "plausibility",
  "integrity",
] as const

const CATEGORY_LABEL: Record<string, string> = {
  privacy: "Privacy & pseudonymization",
  completeness: "Structural completeness",
  plausibility: "Plausibility",
  integrity: "Referential integrity",
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
            [ruleKey]: { ...previous.rules[ruleKey], ...update },
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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              {resourceType}
            </h1>
            {data?.is_server_specific ? (
              <Badge variant="secondary">Server override</Badge>
            ) : (
              <Badge variant="outline">Global defaults</Badge>
            )}
          </div>
          {data?.is_server_specific && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
            >
              <Restart className="mr-2 h-4 w-4" />
              {resetMutation.isPending ? "Resetting..." : "Reset to defaults"}
            </Button>
          )}
        </div>
        <p className="mx-auto flex max-w-6xl text-sm text-muted-foreground">
          Toggle rules, change their severity, and edit regex patterns. Each
          change is saved immediately for this server.
        </p>
      </div>

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

      {data &&
        CATEGORY_ORDER.map((category) => {
          const entries = Object.entries(data.rules).filter(
            ([, rule]) => rule.category === category
          )
          if (entries.length === 0) return null

          return (
            <section
              key={category}
              className="mx-auto max-w-4xl space-y-2 rounded-xl border bg-sidebar-accent/20 px-1 pt-5"
            >
              <h2
                className={cn(
                  "px-4 py-2 text-xs font-medium tracking-wide text-muted-foreground capitalize",
                  category === "privacy"
                    ? "text-rose-500"
                    : category === "completeness"
                      ? "text-orange-500"
                      : "text-blue-500"
                )}
              >
                {CATEGORY_LABEL[category] ?? category}
              </h2>
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
                            SEVERITY_TEXT[rule.severity as Severity]
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
    </div>
  )
}
