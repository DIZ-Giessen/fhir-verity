import { Link, createFileRoute } from "@tanstack/react-router"
import { ChevronLeft } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"

export const Route = createFileRoute("/runs/$runId")({
  component: RunDetailPlaceholder,
})

function RunDetailPlaceholder() {
  const { runId } = Route.useParams()
  return (
    <div className="space-y-4">
      <Link
        to="/runs"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="mr-1 h-4 w-4" />
        Back to runs
      </Link>
      <Card>
        <CardContent className="space-y-1 py-8 text-center">
          <p className="text-sm font-medium">Run detail page</p>
          <p className="font-mono text-xs text-muted-foreground">{runId}</p>
          <p className="pt-2 text-xs text-muted-foreground">
            Detailed view (run summary, invalid resources, per-rule breakdown)
            is coming next.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
