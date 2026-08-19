export const SEVERITY_STYLES: Record<string, string> = {
  error:
    "border-0 bg-red-500/15 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  warning:
    "border-0 bg-amber-500/15 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
  info: "border-0 bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
}

export const SEVERITY_ORDER: Record<string, number> = {
  error: 0,
  warning: 1,
  info: 2,
}
