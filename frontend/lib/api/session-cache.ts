"use client"

import { getSession } from "next-auth/react"

const SESSION_CACHE_WINDOW_MS = 10_000
let cachedSession:
  | Awaited<ReturnType<typeof getSession>>
  | undefined
let cachedSessionAt = 0
let inFlightSessionRequest: Promise<Awaited<ReturnType<typeof getSession>>> | null = null

export const readSessionForApi = async () => {
  const now = Date.now()
  if (cachedSession !== undefined && now - cachedSessionAt < SESSION_CACHE_WINDOW_MS) {
    return cachedSession
  }
  if (inFlightSessionRequest) {
    return inFlightSessionRequest
  }
  inFlightSessionRequest = getSession()
    .then((session) => {
      cachedSession = session
      cachedSessionAt = Date.now()
      return session
    })
    .finally(() => {
      inFlightSessionRequest = null
    })
  return inFlightSessionRequest
}

export const resetApiSessionCacheForTests = () => {
  cachedSession = undefined
  cachedSessionAt = 0
  inFlightSessionRequest = null
}
