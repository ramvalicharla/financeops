import { z } from "zod"

import apiClient, { parseWithSchema } from "@/lib/api/client"
import { PipelineRunSchema } from "@/lib/schemas/pipeline"

const paginatedPipelineRunsSchema = z.object({
  data: z.array(PipelineRunSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
})

export const fetchPipelineRuns = async (params?: {
  limit?: number
  offset?: number
}) => {
  const search = new URLSearchParams()
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit))
  }
  if (params?.offset !== undefined) {
    search.set("offset", String(params.offset))
  }
  const endpoint = `/api/v1/pipeline/runs${search.toString() ? `?${search.toString()}` : ""}`
  const response = await apiClient.get<unknown>(endpoint)
  const raw = response.data
  if (Array.isArray(raw)) {
    return raw.map((item) => parseWithSchema(endpoint, item, PipelineRunSchema))
  }
  const parsed = parseWithSchema(endpoint, raw, paginatedPipelineRunsSchema)
  return parsed.data
}

