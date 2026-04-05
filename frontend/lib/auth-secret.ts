const DEV_AUTH_SECRET =
  "dev-nextauth-secret-for-local-only-0123456789abcdef0123456789abcdef"

export const getAuthSecret = (): string => {
  const nextAuthSecret = process.env.NEXTAUTH_SECRET?.trim()
  if (nextAuthSecret) {
    return nextAuthSecret
  }

  const authSecret = process.env.AUTH_SECRET?.trim()
  if (authSecret) {
    return authSecret
  }

  if (process.env.NODE_ENV !== "production") {
    return DEV_AUTH_SECRET
  }

  throw new Error(
    "NEXTAUTH_SECRET or AUTH_SECRET must be configured in production.",
  )
}
