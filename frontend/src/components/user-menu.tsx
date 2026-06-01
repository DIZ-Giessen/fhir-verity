import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ChevronDown, LogOut } from "lucide-react"

import { logout, meQueryOptions } from "@/api/queries"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { initials } from "@/lib/functions"

const ROLE_STYLES: Record<string, string> = {
  admin:
    "border-0 bg-rose-500/15 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400",
  editor:
    "border-0 bg-amber-500/15 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
  viewer:
    "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
}

export function UserMenu() {
  const { data: user } = useQuery(meQueryOptions())
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      queryClient.clear()
      await navigate({ to: "/login" })
    },
  })

  if (!user) return null

  const displayName = user.full_name || user.username || user.email || "User"

  console.log(user)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" className="h-auto gap-2 px-2 py-1.5">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="text-xs">
              {initials(user.username)}
            </AvatarFallback>
          </Avatar>
          <span className="text-sm font-medium">
            {user.username ?? displayName}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0">
        <div className="space-y-3 p-4">
          <div className="flex items-center gap-3">
            <Avatar className="h-10 w-10">
              <AvatarFallback>{initials(user.username)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1 space-y-0.5">
              <p className="truncate text-sm font-medium">{displayName}</p>
              {user.email && (
                <p className="truncate text-xs text-muted-foreground">
                  {user.email}
                </p>
              )}
            </div>
          </div>
          <div className="pt-2text-xs hidden items-center justify-end">
            <span className="hidden text-muted-foreground">Role</span>
            <Badge variant="outline" className={ROLE_STYLES[user.role] ?? ""}>
              {user.role}
            </Badge>
          </div>
        </div>
        <Separator />
        <div className="p-1">
          <Button
            variant="ghost"
            className="w-full justify-start text-destructive hover:text-destructive"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
          >
            <LogOut className="mr-2 h-4 w-4" />
            {logoutMutation.isPending ? "Signing out…" : "Sign out"}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
