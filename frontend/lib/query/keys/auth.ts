// Auth — identity and session state.
// No current inline query key usages — kept as stubs for future auth query hooks.

export const authKeys = {
  me: () => ["auth", "me"] as const,
  session: () => ["auth", "session"] as const,
} as const
