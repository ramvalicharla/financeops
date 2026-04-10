"use client"

const AUTH_RECOVERY_WINDOW_MS = 30_000
const MAX_AUTH_RECOVERY_ATTEMPTS = 2

type AuthRecoveryKind = "sign_out" | "org_setup_redirect"

type GuardState = {
  count: number
  startedAt: number
}

const guardState = new Map<string, GuardState>()

const buildKey = (kind: AuthRecoveryKind, scope: string): string =>
  `${kind}:${scope || "global"}`

export const consumeAuthRecoveryAttempt = (
  kind: AuthRecoveryKind,
  scope: string,
  now = Date.now(),
): boolean => {
  const key = buildKey(kind, scope)
  const current = guardState.get(key)

  if (!current || now - current.startedAt > AUTH_RECOVERY_WINDOW_MS) {
    guardState.set(key, { count: 1, startedAt: now })
    return true
  }

  if (current.count >= MAX_AUTH_RECOVERY_ATTEMPTS) {
    return false
  }

  current.count += 1
  guardState.set(key, current)
  return true
}

export const resetAuthRecoveryGuardForTests = (): void => {
  guardState.clear()
}
