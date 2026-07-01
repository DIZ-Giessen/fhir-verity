import { Link, useRouterState } from "@tanstack/react-router"
import { type LucideIcon } from "lucide-react"

import {
  Server2,
  PieChart2,
  PlayCircle,
  NotificationLinesRemove,
  ClipboardList,
} from "@solar-icons/react-perf/category/style/LineDuotone"

import { cn } from "@/lib/utils"
import { Badge } from "./ui/badge"

type Role = 1 | 2 | 3

type NavItem = {
  to: "/" | "/servers" | "/runs" | "/cleanup" | "/audit"
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
    minRole: 2,
  },
  { to: "/audit", label: "Audit", icon: ClipboardList, minRole: 3 },
]

interface MainNavProps {
  role?: Role
}

export function MainNav({ role = 3 }: MainNavProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  const visible = navItems.filter(
    (item) => item.minRole === undefined || role >= item.minRole
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
            <Icon className="size-4" aria-hidden />
            <span>{item.label}</span>
            {item.to === "/cleanup" && (
              <Badge
                variant="outline"
                className="absolute -top-1.5 -right-3 scale-75 border-orange-500 text-[10px] text-orange-500"
              >
                BETA
              </Badge>
            )}
          </Link>
        )
      })}
    </nav>
  )
}
