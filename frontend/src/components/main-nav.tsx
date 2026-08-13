import { useQuery } from "@tanstack/react-query"
import { Link, useRouterState } from "@tanstack/react-router"
import { type LucideIcon } from "lucide-react"

import {
  Server2,
  PieChart2,
  PlayCircle,
  NotificationLinesRemove,
  Database,
  ClipboardList,
  UsersGroupRounded,
} from "@solar-icons/react-perf/category/style/LineDuotone"

import { hasRole, meQueryOptions, type Role } from "@/api/queries"
import { cn } from "@/lib/utils"

type NavItem = {
  to:
    | "/"
    | "/servers"
    | "/runs"
    | "/cleanup"
    | "/db-cleanup"
    | "/audit"
    | "/users"
  label: string
  icon: LucideIcon
  minRole?: Role
}

const navItems: NavItem[] = [
  { to: "/", label: "Overview", icon: PieChart2 },
  { to: "/servers", label: "Servers", icon: Server2 },
  { to: "/runs", label: "Runs", icon: PlayCircle },
  {
    to: "/cleanup",
    label: "Cleanup",
    icon: NotificationLinesRemove,
    minRole: "editor",
  },
  {
    to: "/db-cleanup",
    label: "DB Cleanup",
    icon: Database,
    minRole: "admin",
  },
  { to: "/audit", label: "Audit", icon: ClipboardList, minRole: "admin" },
  { to: "/users", label: "Users", icon: UsersGroupRounded, minRole: "admin" },
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
              className={cn("size-4", item.to === "/runs" ? "size-4.5" : "")}
              aria-hidden
            />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
