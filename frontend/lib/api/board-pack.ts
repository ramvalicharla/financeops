import { z } from "zod"
import apiClient, { parseWithSchema } from "@/lib/api/client"
import { BoardPackRunSchema } from "@/lib/schemas/board_pack"
import type {
  ArtifactResponse,
  CreateDefinitionRequest,
  DefinitionResponse,
  GenerateRequest,
  RunResponse,
  SectionResponse,
  UpdateDefinitionRequest,
} from "@/lib/types/board-pack"

const paginatedRunsSchema = z.object({
  data: z.array(BoardPackRunSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
})

const extractList = <T>(payload: T[] | { data: T[] }): T[] =>
  Array.isArray(payload) ? payload : payload.data

export const fetchDefinitions = async (
  activeOnly = true,
): Promise<DefinitionResponse[]> => {
  const response = await apiClient.get<DefinitionResponse[]>(
    `/api/v1/board-packs/definitions?active_only=${activeOnly ? "true" : "false"}`,
  )
  return response.data
}

export const createDefinition = async (
  body: CreateDefinitionRequest,
): Promise<DefinitionResponse> => {
  const response = await apiClient.post<DefinitionResponse>(
    "/api/v1/board-packs/definitions",
    body,
  )
  return response.data
}

export const updateDefinition = async (
  id: string,
  body: UpdateDefinitionRequest,
): Promise<DefinitionResponse> => {
  const response = await apiClient.patch<DefinitionResponse>(
    `/api/v1/board-packs/definitions/${id}`,
    body,
  )
  return response.data
}

export const deleteDefinition = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/v1/board-packs/definitions/${id}`)
}

export const generatePack = async (body: GenerateRequest): Promise<RunResponse> => {
  const response = await apiClient.post<RunResponse>(
    "/api/v1/board-packs/generate",
    body,
  )
  return response.data
}

export const fetchRuns = async (params?: {
  definition_id?: string
  status?: string
  limit?: number
}): Promise<RunResponse[]> => {
  const search = new URLSearchParams()
  if (params?.definition_id) {
    search.set("definition_id", params.definition_id)
  }
  if (params?.status) {
    search.set("status", params.status)
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit))
  }
  const query = search.toString()
  const endpoint = `/api/v1/board-packs/runs${query ? `?${query}` : ""}`
  const response = await apiClient.get<unknown>(endpoint)
  const raw = response.data
  if (Array.isArray(raw)) {
    return raw.map((item) =>
      parseWithSchema(endpoint, item, BoardPackRunSchema),
    ) as unknown as RunResponse[]
  }
  const parsed = parseWithSchema(endpoint, raw, paginatedRunsSchema)
  return parsed.data as unknown as RunResponse[]
}

export const fetchRun = async (id: string): Promise<RunResponse> => {
  const endpoint = `/api/v1/board-packs/runs/${id}`
  const response = await apiClient.get<unknown>(endpoint)
  return parseWithSchema(endpoint, response.data, BoardPackRunSchema) as unknown as RunResponse
}

export const fetchSections = async (runId: string): Promise<SectionResponse[]> => {
  const response = await apiClient.get<SectionResponse[] | { data: SectionResponse[] }>(
    `/api/v1/board-packs/runs/${runId}/sections`,
  )
  return extractList(response.data)
}

export const fetchArtifacts = async (runId: string): Promise<ArtifactResponse[]> => {
  const response = await apiClient.get<ArtifactResponse[] | { data: ArtifactResponse[] }>(
    `/api/v1/board-packs/runs/${runId}/artifacts`,
  )
  return extractList(response.data)
}

export const downloadArtifact = async (
  runId: string,
  format: "pdf" | "excel",
): Promise<Blob> => {
  const response = await apiClient.get<Blob>(
    `/api/v1/board-packs/runs/${runId}/download/${format}`,
    {
      responseType: "blob",
    },
  )
  return response.data
}
