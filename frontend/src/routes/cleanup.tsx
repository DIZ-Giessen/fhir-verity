import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/cleanup')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/cleanup"!</div>
}
