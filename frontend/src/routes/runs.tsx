import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/runs')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/runs"!</div>
}
