import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { resourceTypesQueryOptions, serverQueryOptions } from "@/api/queries"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api-client"

export const Route = createFileRoute("/servers/$id/config/")({
  component: ConfigOverviewPage,
})

function ConfigOverviewPage() {
  const { id } = Route.useParams()
  const { data, isPending, error } = useQuery(resourceTypesQueryOptions())
  const serverQ = useQuery(serverQueryOptions(id))
  const serverName = serverQ.data?.name ?? id.slice(0, 8)

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          to="/servers/$id"
          params={{ id }}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back to server
        </Link>
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            Validation configuration for the server:{" "}
            <span className="text-orange-500">{serverName}</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            Select a resource type to review and adjust its validation rules.
            Changes apply only to this server.
          </p>
        </div>
      </div>

      {isPending && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border p-8 text-center">
          <p className="text-sm font-medium text-destructive">
            Failed to load resource types
          </p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {error instanceof ApiError
              ? `HTTP ${error.status} — ${error.statusText}`
              : error.message}
          </p>
        </div>
      )}

      {data && (
        <div className="mx-auto max-w-7xl divide-y overflow-hidden rounded-lg border">
          {data.map((rt) => (
            <Link
              key={rt}
              to="/servers/$id/config/$resourceType"
              params={{ id, resourceType: rt }}
              className="flex items-center justify-between p-4 transition-colors hover:bg-muted/50"
            >
              <span className="font-medium">{rt}</span>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
