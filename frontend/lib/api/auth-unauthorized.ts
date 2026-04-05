type UnauthorizedRequest = {
  config?: {
    headers?: unknown
    url?: string
  }
  response?: {
    status?: number
  }
}

const isAxiosHeaders = (
  headers: unknown,
): headers is { get: (name: string) => unknown } =>
  Boolean(headers) &&
  typeof headers === "object" &&
  typeof (headers as { get?: unknown }).get === "function"

const getHeaderValue = (headers: unknown, name: string): string | undefined => {
  if (!headers || typeof headers !== "object") {
    return undefined
  }

  if (isAxiosHeaders(headers)) {
    const value = headers.get(name)
    return typeof value === "string" ? value : undefined
  }

  const record = headers as Record<string, unknown>
  const value = record[name] ?? record[name.toLowerCase()]
  return typeof value === "string" ? value : undefined
}

const getRequestPath = (url: string | undefined, baseUrl: string): string => {
  if (!url) {
    return ""
  }

  try {
    return new URL(url, baseUrl || "http://localhost").pathname
  } catch {
    return url
  }
}

export const shouldSignOutOnUnauthorized = (
  error: UnauthorizedRequest,
  baseUrl: string,
): boolean => {
  if (error.response?.status !== 401) {
    return false
  }

  const requestPath = getRequestPath(error.config?.url, baseUrl)
  if (requestPath.startsWith("/api/v1/auth/")) {
    return false
  }

  const authorizationHeader = getHeaderValue(error.config?.headers, "Authorization")
  return Boolean(authorizationHeader?.trim())
}
