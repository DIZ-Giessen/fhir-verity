// Interface  for the APP

// ---------------------------------------------------------------------------
// Test Report Interface
// ---------------------------------------------------------------------------

export interface ResourceRef {
  server_id?: string | null
}

export interface TestScriptEntry extends ResourceRef {
  url?: string
  version?: string
  /** true when an existing TestScript with the same url and version was used */
  reused?: boolean
}

export interface TestReportEntry extends ResourceRef {
  result?: string
  score?: number
  violation_counts?: Record<string, number>
}

export interface TestReportSummary {
  run_id?: string
  generated_at?: string
  /** false when the server had "Write FHIR reports" switched off for this run */
  posted_to_server?: boolean
  test_scripts?: Record<string, TestScriptEntry>
  test_reports?: Record<string, TestReportEntry>
  /** List resource referencing all TestReports of the run */
  run_list?: ResourceRef | null
  has_errors?: boolean
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
  sort_dir?: "asc" | "desc"
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
