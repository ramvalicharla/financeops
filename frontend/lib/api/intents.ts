import apiClient from "@/lib/api/client"
import type {
  CreateJournalPayload,
  GovernedMutationResponse,
} from "@/lib/api/accounting-journals"

export type JournalIntentPayload =
  | {
      type: "CREATE_JOURNAL"
      data: CreateJournalPayload
    }
  | {
      type:
        | "SUBMIT_JOURNAL"
        | "REVIEW_JOURNAL"
        | "APPROVE_JOURNAL"
        | "POST_JOURNAL"
        | "REVERSE_JOURNAL"
      data: {
        journal_id: string
      }
    }

type JournalIntentType = JournalIntentPayload["type"]
type CreateJournalIntentPayload = Extract<JournalIntentPayload, { type: "CREATE_JOURNAL" }>
type TransitionJournalIntentPayload = Exclude<JournalIntentPayload, { type: "CREATE_JOURNAL" }>

const JOURNAL_INTENT_ROUTE_MAP: Record<JournalIntentType, string> = {
  CREATE_JOURNAL: "/api/v1/accounting/journals/",
  SUBMIT_JOURNAL: "/submit",
  REVIEW_JOURNAL: "/review",
  APPROVE_JOURNAL: "/approve",
  POST_JOURNAL: "/post",
  REVERSE_JOURNAL: "/reverse",
}

const resolveIntentRoute = (
  payload: JournalIntentPayload,
): { path: string; body: object } => {
  if (payload.type === "CREATE_JOURNAL") {
    const createPayload = payload as CreateJournalIntentPayload
    return {
      path: JOURNAL_INTENT_ROUTE_MAP.CREATE_JOURNAL,
      body: createPayload.data,
    }
  }

  const transitionPayload = payload as TransitionJournalIntentPayload
  return {
    path: `/api/v1/accounting/journals/${transitionPayload.data.journal_id}${JOURNAL_INTENT_ROUTE_MAP[transitionPayload.type]}`,
    body: {},
  }
}

const postGovernedIntent = async (
  path: string,
  payload: object,
): Promise<GovernedMutationResponse> => {
  const response = await apiClient.post<GovernedMutationResponse>(path, payload)
  return response.data
}

export const createGovernedIntent = async (
  payload: JournalIntentPayload,
): Promise<GovernedMutationResponse> => {
  // Backend contract reality for Phase 0:
  // there is no mounted generic POST /api/v1/platform/control-plane/intents
  // route in the current backend. This adapter keeps journal UI intent-first by
  // mapping explicit intent types to the existing governed journal endpoints.
  const { path, body } = resolveIntentRoute(payload)
  return postGovernedIntent(path, body)
}

if (process.env.NODE_ENV === "development") {
  console.warn(
    "[Governance] Using createGovernedIntent() - direct mutation is disabled.",
  )
}

/**
 * @deprecated Use createGovernedIntent().
 * Kept only as a compatibility alias while Phase 0 settles.
 */
export const createIntent = createGovernedIntent
