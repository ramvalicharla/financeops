import apiClient from "@/lib/api/client"
import type {
  BenchmarkResult,
  LearningBenchRunResponse,
  LearningSignalSummary,
  PaginatedResponse,
} from "@/lib/types/learning"

export const runLearningBenchmarks = async (): Promise<LearningBenchRunResponse> => {
  const response = await apiClient.post<LearningBenchRunResponse>(
    "/api/v1/learning/benchmark/run",
  )
  return response.data
}

export const listLearningBenchmarkResults = async (params?: {
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<BenchmarkResult>> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 50))
  search.set("offset", String(params?.offset ?? 0))
  const response = await apiClient.get<PaginatedResponse<BenchmarkResult>>(
    `/api/v1/learning/benchmark/results?${search.toString()}`,
  )
  return response.data
}

export const listRecentLearningSignals = async (params?: {
  limit?: number
}): Promise<LearningSignalSummary[]> => {
  const search = new URLSearchParams()
  search.set("limit", String(params?.limit ?? 30))
  const response = await apiClient.get<{ signals: LearningSignalSummary[] }>(
    `/api/v1/learning/signals/recent?${search.toString()}`,
  )
  return response.data.signals
}

