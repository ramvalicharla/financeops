export type LearningSignalSummary = {
  id: string
  tenant_id: string
  signal_type: string
  task_type: string
  model_used: string
  provider: string
  prompt_tokens: number
  completion_tokens: number
  created_at: string
}

export type BenchmarkResult = {
  id: string
  benchmark_name: string
  benchmark_version: string
  model: string
  provider: string
  total_cases: number
  passed_cases: number
  accuracy_pct: string
  avg_latency_ms: string
  total_cost_usd: string
  run_at: string
  run_by: string
}

export type PaginatedResponse<T> = {
  data: T[]
  total: number
  limit: number
  offset: number
}

export type LearningBenchRunResponse = {
  task_id: string
  status: string
  results: Array<{
    id: string
    benchmark_name: string
    accuracy_pct: string
  }>
}

