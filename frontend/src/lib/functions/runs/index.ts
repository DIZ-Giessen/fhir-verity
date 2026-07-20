export const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

export const monthLabelFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
})

export function formatDuration(
  startISO: string,
  endISO: string | null
): string {
  if (!endISO) return "—"
  const sec = Math.round(
    (new Date(endISO).getTime() - new Date(startISO).getTime()) / 1000
  )
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}m ${sec % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

export const RUN_STATUS_STYLES: Record<string, string> = {
  completed:
    "border-0 bg-emerald-500/5 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
  running:
    "border-0 bg-blue-500/5 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400",
  cancelled:
    "border-0 bg-neutral-500/5 text-neutral-700 dark:bg-neutral-500/10 dark:text-neutral-400",
  failed:
    "border-0 bg-rose-500/5 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400",
}
