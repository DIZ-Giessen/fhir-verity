// Interface  for the APP

// ---------------------------------------------------------------------------
// Test Report Interface
// ---------------------------------------------------------------------------

export interface ResourceRef {
  local_id?: string
  server_id?: string | null
  url?: string
}

export interface TestReportEntry extends ResourceRef {
  result?: string
  score?: number
  violation_counts?: Record<string, number>
}

export interface TestReportSummary {
  run_id?: string
  generated_at?: string
  test_scripts?: Record<string, ResourceRef>
  test_reports?: Record<string, TestReportEntry>
  verification_result?: {
    local_id?: string
    server_id?: string | null
    status?: string
    has_errors?: boolean
  } | null
}

// ---------------------------------------------------------------------------
export interface MonthlyBucket {
  key: string
  label: string
  invalid: number
  date: Date
  runs: number
}

export interface InvalidResourcesParams {
  skip?: number
  limit?: number
  resource_types?: Array<string> | null
  rule?: string | null
  severity?: string | null
  only_current_run?: boolean
  sort_by?: string | null
  sort_dir?: "asc" | "desc" | null
}

// ?  LIVE PROGRESS
export interface MetricPoint {
  time: number
  processed: number
  invalid: number
  rps: number
}

export interface LiveMetrics {
  totalProcessed: number
  totalInvalid: number
  rps: number | null
  elapsedSeconds: number | null
  currentResource: string | null
  pagesDone: number | null
  progressPercent: number | null
  etaSeconds: number | null
}

export interface LogEntry {
  id: number
  time: string
  type: string
  msg: string
}
