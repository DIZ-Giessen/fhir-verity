import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react"

import { TableHead } from "@/components/ui/table"
import { cn } from "@/lib/utils"

export type SortDir = "asc" | "desc"

/** Clickable column header with a sort-direction indicator, TanStack-table style. */
export function SortableTableHead({
  label,
  sortKey,
  activeKey,
  dir,
  onSort,
  className,
  align = "left",
}: {
  label: string
  sortKey: string
  activeKey: string
  dir: SortDir
  onSort: (key: string) => void
  className?: string
  align?: "left" | "right"
}) {
  const isActive = activeKey === sortKey
  return (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground",
          align === "right" && "flex-row-reverse",
          isActive ? "text-foreground" : "text-muted-foreground"
        )}
      >
        {label}
        {isActive ? (
          dir === "asc" ? (
            <ChevronUp className="size-3.5" />
          ) : (
            <ChevronDown className="size-3.5" />
          )
        ) : (
          <ChevronsUpDown className="size-3.5 opacity-40" />
        )}
      </button>
    </TableHead>
  )
}

/** Toggle sort state on header click: same column flips direction, new column
 * starts at `defaultDir` (or "desc" for numeric-feeling columns like counts). */
export function nextSort(
  current: { key: string; dir: SortDir },
  key: string,
  defaultDir: SortDir = "asc"
): { key: string; dir: SortDir } {
  if (current.key !== key) return { key, dir: defaultDir }
  return { key, dir: current.dir === "asc" ? "desc" : "asc" }
}
