export type SearchModuleType =
  | "journal"
  | "expense"
  | "report"
  | "user"
  | "entity"
  | string

export interface SearchResultRow {
  id: string
  module: SearchModuleType
  title: string
  subtitle: string | null
  href: string
  status: string | null
  amount: number | null
  currency: string | null
  created_at: string
}

export interface SearchResultMeta {
  query: string
  total_results: number
  limit: number
  offset: number
  query_time_ms: number
}

export interface UnifiedSearchResponse {
  data: SearchResultRow[]
  meta: SearchResultMeta
}

