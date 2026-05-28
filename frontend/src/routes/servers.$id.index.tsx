import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/servers/$id/")({
  component: ServerDetailPage,
})

function ServerDetailPage() {
  const { id } = Route.useParams()

  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">Server detail</h1>
      <p className="text-sm text-muted-foreground">
        Detail view for server <code className="font-mono text-xs">{id}</code> —
        coming soon
      </p>
    </div>
  )
}
