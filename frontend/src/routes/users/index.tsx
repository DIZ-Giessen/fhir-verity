import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import {
  type AuthUser,
  type Role,
  meQueryOptions,
  updateUserRole,
  userKeys,
  usersQueryOptions,
} from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ApiError } from "@/lib/api-client"

export const Route = createFileRoute("/users/")({
  component: UsersPage,
})

const ROLES: Role[] = ["viewer", "editor", "admin"]

function UsersPage() {
  const { data: me } = useQuery(meQueryOptions())
  const isAdmin = me?.role === "admin"

  const {
    data: users,
    isPending,
    error,
  } = useQuery({ ...usersQueryOptions(), enabled: isAdmin })

  if (me && !isAdmin) {
    return (
      <div className="rounded-lg border p-8 text-center">
        <p className="text-sm font-medium">Access denied</p>
        <p className="mt-1 text-sm text-muted-foreground">
          User management is restricted to administrators.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <p className="text-sm text-muted-foreground">
          Manage access roles across FHIR Verity
        </p>
      </div>

      {isPending && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border p-8 text-center">
          <p className="text-sm font-medium text-destructive">
            Failed to load users
          </p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {error instanceof ApiError
              ? `HTTP ${error.status} — ${error.statusText}`
              : error.message}
          </p>
        </div>
      )}

      {users && me && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Email</TableHead>
                <TableHead className="w-40">Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <UserRow key={u.id} user={u} currentUserId={me.id} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

function UserRow({
  user,
  currentUserId,
}: {
  user: AuthUser
  currentUserId: string
}) {
  const qc = useQueryClient()
  const isSelf = user.id === currentUserId

  const mutation = useMutation({
    mutationFn: (role: Role) => updateUserRole(user.id, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  })

  return (
    <TableRow>
      <TableCell className="font-medium">
        <span className="flex items-center gap-2">
          {user.full_name || user.username || "—"}
          {isSelf && <Badge variant="secondary">You</Badge>}
        </span>
      </TableCell>
      <TableCell className="text-muted-foreground">
        {user.email || "—"}
      </TableCell>
      <TableCell>
        <Select
          value={user.role}
          onValueChange={(v) => mutation.mutate(v as Role)}
          disabled={isSelf || mutation.isPending}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r} className="capitalize">
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {mutation.isError && (
          <p className="mt-1 text-xs text-destructive">
            {mutation.error instanceof ApiError
              ? `HTTP ${mutation.error.status} — änderung abgelehnt`
              : "Update failed"}
          </p>
        )}
      </TableCell>
    </TableRow>
  )
}
