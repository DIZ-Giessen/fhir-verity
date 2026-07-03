export function initials(name: string | null | undefined): string {
  if (!name) return "U"
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "U"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export const MOMENTUM = {
  up: "var(--color-emerald-500, #10b981)",
  down: "var(--color-red-500, #ef4444)",
  flat: "var(--color-zinc-400, #a1a1aa)",
} as const
