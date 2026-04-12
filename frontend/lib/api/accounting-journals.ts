import apiClient from "@/lib/api/client"

export interface JournalLineInput {
  account_code?: string
  tenant_coa_account_id?: string
  debit: string
  credit: string
  memo?: string
  transaction_currency?: string
  functional_currency?: string
  fx_rate?: string
  base_amount?: string
}

export interface CreateJournalPayload {
  org_entity_id: string
  journal_date: string
  reference?: string
  narration?: string
  lines: JournalLineInput[]
}

export interface JournalLine {
  line_number: number
  tenant_coa_account_id: string | null
  account_code: string
  account_name: string | null
  debit: string
  credit: string
  memo: string | null
  transaction_currency: string | null
  functional_currency: string | null
  fx_rate: string | null
  base_amount: string | null
}

export interface JournalRecord {
  id: string
  org_entity_id: string
  journal_number: string
  journal_date: string
  reference: string | null
  narration: string | null
  status: string
  posted_at: string | null
  total_debit: string
  total_credit: string
  currency: string
  created_by?: string | null
  intent_id?: string | null
  job_id?: string | null
  approval_status?: string | null
  lines: JournalLine[]
}

export interface GovernedMutationResponse {
  intent_id: string
  status: string
  job_id: string | null
  next_action: string
  record_refs: Record<string, unknown> | null
}

export const listJournals = async (params?: {
  org_entity_id?: string
  status?: "DRAFT" | "SUBMITTED" | "REVIEWED" | "APPROVED" | "POSTED" | "REVERSED"
  limit?: number
  offset?: number
}): Promise<JournalRecord[]> => {
  const search = new URLSearchParams()
  if (params?.org_entity_id) search.set("org_entity_id", params.org_entity_id)
  if (params?.status) search.set("status", params.status)
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  const suffix = search.toString()
  const response = await apiClient.get<JournalRecord[]>(
    `/api/v1/accounting/journals/${suffix ? `?${suffix}` : ""}`,
  )
  return response.data
}

export const getJournal = async (journalId: string): Promise<JournalRecord> => {
  const response = await apiClient.get<JournalRecord>(
    `/api/v1/accounting/journals/${journalId}`,
  )
  return response.data
}

function forbiddenDirectMutation(operation: string): never {
  throw new Error(
    `[Governance Violation] Direct mutation "${operation}" is forbidden.\n` +
      `Use createGovernedIntent() instead.`,
  )
}

const deprecatedCreateJournalMutation = async (
  _payload: CreateJournalPayload,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("createJournal")

const deprecatedApproveJournalMutation = async (
  _journalId: string,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("approveJournal")

const deprecatedSubmitJournalMutation = async (
  _journalId: string,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("submitJournal")

const deprecatedReviewJournalMutation = async (
  _journalId: string,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("reviewJournal")

const deprecatedPostJournalMutation = async (
  _journalId: string,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("postJournal")

const deprecatedReverseJournalMutation = async (
  _journalId: string,
): Promise<GovernedMutationResponse> => forbiddenDirectMutation("reverseJournal")

/**
 * @deprecated DO NOT USE - use createGovernedIntent() from @/lib/api/intents.
 * Kept as a backward-compatible export and blocked at runtime.
 */
export {
  deprecatedApproveJournalMutation as approveJournal,
  deprecatedCreateJournalMutation as createJournal,
  deprecatedPostJournalMutation as postJournal,
  deprecatedReviewJournalMutation as reviewJournal,
  deprecatedReverseJournalMutation as reverseJournal,
  deprecatedSubmitJournalMutation as submitJournal,
}
