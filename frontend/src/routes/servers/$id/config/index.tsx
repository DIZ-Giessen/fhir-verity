import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { toast } from "sonner"

import type { FhirServer } from "@/api/queries"
import {
  resourceTypesQueryOptions,
  serverKeys,
  serverQueryOptions,
  updateServer,
} from "@/api/queries"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { ApiError, apiErrorMessage } from "@/lib/api-client"

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

      <div className="mx-auto max-w-7xl">
        {serverQ.data ? (
          <FhirReportsSetting server={serverQ.data} />
        ) : (
          <Skeleton className="h-24 w-full" />
        )}
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

function FhirReportsSetting({ server }: { server: FhirServer }) {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (enabled: boolean) =>
      updateServer(server.id, { write_fhir_reports: enabled }),
    onSuccess: (updated, enabled) => {
      if (updated)
        queryClient.setQueryData(serverKeys.detail(server.id), updated)
      queryClient.invalidateQueries({ queryKey: serverKeys.all })
      if (enabled) {
        toast.success("FHIR reports enabled", {
          description: `From the next completed run on, a TestReport per resource type and one List for the run are written to ${server.name}. TestScripts are only written when the rule configuration changed.`,
        })
      } else {
        toast.success("FHIR reports disabled", {
          description: `Nothing will be written to ${server.name} anymore. Scores and results of each run remain visible in Verity.`,
        })
      }
    },
    onError: (err) => {
      toast.error("Could not change the report setting", {
        description: apiErrorMessage(err),
      })
    },
  })

  // Show the requested state while the PATCH is in flight
  const checked = mutation.isPending
    ? mutation.variables
    : server.write_fhir_reports

  return (
    <Card className="shadow-none">
      <CardContent className="flex items-start justify-between gap-6">
        <div className="space-y-1">
          <Label htmlFor="write-fhir-reports" className="text-base">
            Write FHIR reports to the server
          </Label>
          <p className="text-sm text-muted-foreground">
            After each completed run, Verity posts the results as FHIR resources
            to this server: one <b>TestReport</b> per validated resource type
            and one <b>List</b> referencing them for the whole run. The rules
            are described by one <b>TestScript</b> per resource type, which is
            reused as long as the configuration does not change. Turn this off
            for read-only or production servers where Verity must not create any
            resources. The results remain visible in Verity either way.
          </p>
        </div>
        <Switch
          id="write-fhir-reports"
          checked={checked}
          disabled={mutation.isPending}
          onCheckedChange={(value) => mutation.mutate(value)}
          aria-label="Write FHIR reports to the server"
        />
      </CardContent>
    </Card>
  )
}
