import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "@tanstack/react-router"
import { ChevronDown, LogOut, Play } from "lucide-react"
import { useState } from "react"

import {
  Broom,
  ClipboardList,
  ServerPath,
  UsersGroupRounded,
} from "@solar-icons/react-perf/category/style/LineDuotone"
import type { NotificationLinesRemove } from "@solar-icons/react-perf/category/style/LineDuotone"

import type { AuthUser, Role } from "@/api/queries"
import {
  authConfigQueryOptions,
  authKeys,
  hasRole,
  logout,
  meQueryOptions,
  updateMyPreferences,
} from "@/api/queries"
import { StartValidationDialog } from "@/components/start-validation-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { initials } from "@/lib/functions"

type ManagementItem = {
  to: "/cleanup" | "/db-cleanup" | "/audit" | "/users"
  label: string
  icon: typeof NotificationLinesRemove
  minRole: Role
}

const managementItems: Array<ManagementItem> = [
  {
    to: "/cleanup",
    label: "Cleanup Page",
    icon: Broom,
    minRole: "editor",
  },
  {
    to: "/db-cleanup",
    label: "Database Cleanup",
    icon: ServerPath,
    minRole: "admin",
  },
  { to: "/audit", label: "Audit Page", icon: ClipboardList, minRole: "admin" },
  {
    to: "/users",
    label: "Users Page",
    icon: UsersGroupRounded,
    minRole: "admin",
  },
]

export function UserMenu() {
  const { data: user } = useQuery(meQueryOptions())
  const { data: authConfig } = useQuery(authConfigQueryOptions())
  // Without auth there is no session to end; "Sign out" would just bounce back.
  const canSignOut = authConfig?.auth_enabled !== false
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [menuOpen, setMenuOpen] = useState(false)
  const [startOpen, setStartOpen] = useState(false)

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      queryClient.clear()
      await navigate({ to: "/login" })
    },
  })

  const emailPref = useMutation({
    mutationFn: (enabled: boolean) =>
      updateMyPreferences({ email_notifications_enabled: enabled }),
    onMutate: async (enabled) => {
      await queryClient.cancelQueries({ queryKey: authKeys.me })
      const previous = queryClient.getQueryData<AuthUser>(authKeys.me)
      queryClient.setQueryData<AuthUser>(authKeys.me, (old) =>
        old ? { ...old, email_notifications_enabled: enabled } : old
      )
      return { previous }
    },
    onError: (_err, _enabled, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(authKeys.me, ctx.previous)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: authKeys.me })
    },
  })

  if (!user) return null

  const displayName = user.full_name || user.username || user.email || "User"
  const visibleManagementItems = managementItems.filter((item) =>
    hasRole(user.role, item.minRole)
  )

  return (
    <>
      <Popover open={menuOpen} onOpenChange={setMenuOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" className="h-auto gap-2 px-2 py-1.5">
            <Avatar className="h-8 w-8">
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
          </div>
          {visibleManagementItems.length > 0 && (
            <>
              <Separator />
              <div className="space-y-0.5 p-1">
                {visibleManagementItems.map((item) => {
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 rounded-full px-3 py-1.5 text-sm text-foreground hover:bg-accent/60 hover:text-orange-500"
                    >
                      <Icon className="size-4" aria-hidden />
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </div>
            </>
          )}
          {/* Notifications go to user.email; without one the switch does nothing. */}
          {user.email && (
            <>
              <Separator />
              <div className="flex items-center justify-between gap-3 p-4">
                <div className="space-y-0.5">
                  <Label
                    htmlFor="email-notifications"
                    className="text-sm font-medium"
                  >
                    Email-Benachrichtigungen
                  </Label>
                </div>
                <Switch
                  id="email-notifications"
                  checked={user.email_notifications_enabled}
                  onCheckedChange={(v) => emailPref.mutate(v)}
                  disabled={emailPref.isPending}
                />
              </div>
            </>
          )}
          <Separator />
          <div className="p-1 px-3">
            <Button
              className="w-full"
              onClick={() => {
                setMenuOpen(false)
                setStartOpen(true)
              }}
            >
              <Play className="size-4" />
              Start validation
            </Button>
          </div>
          {canSignOut && (
            <>
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
            </>
          )}
        </PopoverContent>
      </Popover>
      <StartValidationDialog open={startOpen} onOpenChange={setStartOpen} />
    </>
  )
}
