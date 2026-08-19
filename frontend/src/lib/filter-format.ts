const FILTER_LABELS: Record<string, string> = {
  last_updated_from: "Last updated from",
  last_updated_to: "Last updated to",
  profile: "Profile",
  tag: "Tag",
}

export function hasActiveFilters(
  filters: Record<string, unknown> | null | undefined
): filters is Record<string, unknown> {
  return filters != null && Object.keys(filters).length > 0
}

export function filterEntries(
  filters: Record<string, unknown>
): Array<{ label: string; value: string }> {
  return Object.entries(filters)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => ({ label: FILTER_LABELS[k] ?? k, value: String(v) }))
}
