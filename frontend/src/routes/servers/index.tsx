import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"

import { type FhirServer, serversQueryOptions } from "@/api/queries"
import { ServerFormDialog } from "@/components/server-form-dialog"
import { ServersTable } from "@/components/servers-table"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api-client"

export const Route = createFileRoute("/servers/")({
  component: ServersPage,
})

function ServersPage() {
  const { data, isPending, error } = useQuery(serversQueryOptions())

  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<FhirServer | null>(null)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Servers</h1>
          <p className="text-sm text-muted-foreground">
            FHIR servers registered for validation
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add server
        </Button>
      </div>

      {isPending && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border p-8 text-center">
          <p className="text-sm font-medium text-destructive">
            Failed to load servers
          </p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {error instanceof ApiError
              ? `HTTP ${error.status} — ${error.statusText}`
              : error.message}
          </p>
        </div>
      )}

      {data && <ServersTable data={data} onEdit={setEditTarget} />}

      <ServerFormDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ServerFormDialog
        open={editTarget !== null}
        onOpenChange={(open) => !open && setEditTarget(null)}
        server={editTarget ?? undefined}
      />
    </div>
  )
}
