import { useQuery } from "@tanstack/react-query"
import { Link, useRouterState } from "@tanstack/react-router"
import {
  HomeSmileIcon,
  NotificationRemoveIcon,
  PlayCircleIcon,
  ServerSquareIcon,
} from "@solar-icons/react/line-duotone"

import type { Role } from "@/api/queries"
import { hasRole, meQueryOptions } from "@/api/queries"
import { cn } from "@/lib/utils"

type NavItem = {
  to: "/" | "/servers" | "/runs" | "/cleanup"
  label: string
  icon: React.ElementType
  minRole?: Role
}

const navItems: Array<NavItem> = [
  { to: "/", label: "Overview", icon: HomeSmileIcon },
  { to: "/servers", label: "Servers", icon: ServerSquareIcon },
  { to: "/runs", label: "Runs", icon: PlayCircleIcon },
  {
    to: "/cleanup",
    label: "Cleanup",
    icon: NotificationRemoveIcon,
    minRole: "editor",
  },
]

export function MainNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { data: me } = useQuery(meQueryOptions())
  const role = me?.role

  const visible = navItems.filter(
    (item) => item.minRole === undefined || hasRole(role, item.minRole)
  )

  return (
    <nav className="flex items-center gap-1">
      {visible.map((item) => {
        const Icon = item.icon
        const isActive =
          item.to === "/"
            ? pathname === "/"
            : pathname === item.to || pathname.startsWith(`${item.to}/`)

        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "relative inline-flex items-center gap-2 rounded-2xl px-4 py-1.5 text-sm transition-colors ease-in",
              isActive
                ? "bg-accent font-medium text-orange-500"
                : "text-foreground hover:bg-accent/60 hover:text-orange-500"
            )}
          >
            <Icon
              strokeWidth={1.8}
              className={cn("size-5", item.to === "/runs" ? "size-5.5" : "")}
              aria-hidden
            />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
