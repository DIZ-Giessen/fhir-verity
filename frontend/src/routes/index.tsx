import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { Button } from "@/components/ui/button"
import { ApiError, api } from "@/lib/api-client"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  const { data, isPending, error, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await api.GET("/")
      return data
    },
  })

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 p-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">FHIR Verity</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Validation hub for FHIR resources
        </p>
      </div>

      <div className="w-full max-w-md rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-sm font-medium">Backend status</h2>

        {isPending && (
          <p className="text-sm text-muted-foreground">Connecting...</p>
        )}

        {error && (
          <div className="text-sm">
            <p className="font-medium text-destructive">Not reachable</p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {error instanceof ApiError
                ? `HTTP ${error.status} — ${error.statusText}`
                : error.message}
            </p>
          </div>
        )}

        {data && (
          <pre className="overflow-x-auto rounded bg-muted p-3 font-mono text-xs text-muted-foreground">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>

      <Button onClick={() => refetch()} disabled={isFetching}>
        {isFetching ? "Refreshing..." : "Refresh"}
      </Button>
    </div>
  )
}
