import type { Session } from "next-auth"
import { getSession } from "next-auth/react"

const SESSION_WAIT_INTERVAL_MS = 150
const SESSION_WAIT_ATTEMPTS = 12

const delay = (ms: number) =>
  new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })

export const hasEstablishedSession = (
  session: Session | null,
): session is Session =>
  Boolean(
    session?.user?.id &&
      session.user.tenant_id &&
      session.user.tenant_slug &&
      (session.access_token || session.accessToken) &&
      session.refresh_token,
  )

export const waitForEstablishedSession = async (): Promise<Session | null> => {
  for (let attempt = 0; attempt < SESSION_WAIT_ATTEMPTS; attempt += 1) {
    const session = await getSession()
    if (hasEstablishedSession(session)) {
      return session
    }
    if (attempt < SESSION_WAIT_ATTEMPTS - 1) {
      await delay(SESSION_WAIT_INTERVAL_MS)
    }
  }
  return null
}

export const navigateAfterAuth = (callbackUrl: string): void => {
  window.location.assign(callbackUrl)
}
