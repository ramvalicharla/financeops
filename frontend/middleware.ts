import { NextResponse, type NextRequest } from "next/server"
import type { Session } from "next-auth"
import { auth } from "@/lib/auth"

const PUBLIC_PATH_PREFIXES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/auth/change-password",
  "/accept-invite",
  "/mfa",
  "/mfa/setup",
  "/legal",
  "/legal/terms",
  "/legal/privacy",
  "/legal/dpa",
  "/legal/sla",
  "/legal/cookies",
  "/api/auth",
]
const PUBLIC_PATH_EXACT = new Set(["/"])
const ORG_SETUP_PATH = "/org-setup"
const ORG_SETUP_COA_PATH = "/setup/coa"
// The org launcher is accessible to authenticated users regardless of setup
// status — it will redirect first-time users to /org-setup itself after
// fetching their tenant list.
const ORGS_PATH = "/orgs"

const isPublicPath = (pathname: string): boolean =>
  PUBLIC_PATH_EXACT.has(pathname) ||
  PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )

const isStaticAsset = (pathname: string): boolean =>
  pathname.startsWith("/_next") ||
  pathname === "/favicon.ico" ||
  pathname.startsWith("/static")

const normalizeCspConnectSource = (value: string): string => {
  const trimmed = value.trim()
  if (!trimmed) {
    return ""
  }

  try {
    return new URL(trimmed).origin
  } catch {
    return trimmed
  }
}

const applySecurityHeaders = (
  response: NextResponse,
  apiUrl: string | undefined,
): NextResponse => {
  const isProduction = process.env.NODE_ENV === "production"
  const connectSrc = ["'self'"]
  if (apiUrl) {
    const normalizedApiUrl = normalizeCspConnectSource(apiUrl)
    if (normalizedApiUrl) {
      connectSrc.push(normalizedApiUrl)
    }
  }
  if (!isProduction) {
    // Local development often targets changing backends during live testing.
    connectSrc.push("http:", "https:", "ws:", "wss:")
  }
  const scriptSrc = [
    "'self'",
    "'unsafe-inline'",
    "https://static.cloudflareinsights.com",
  ]
  if (!isProduction) {
    scriptSrc.push("'unsafe-eval'")
  }

  response.headers.set("X-Content-Type-Options", "nosniff")
  response.headers.set("X-Frame-Options", "DENY")
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin")
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=()",
  )
  response.headers.set(
    "Strict-Transport-Security",
    "max-age=31536000; includeSubDomains; preload",
  )
  response.headers.set(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      `script-src ${scriptSrc.join(" ")}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self'",
      `connect-src ${connectSrc.join(" ")}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ]
      .filter(Boolean)
      .join("; ")
      .trim(),
  )
  return response
}

const extractTenantSlug = (
  hostname: string,
  headerFallback: string | null,
): string => {
  const normalizedHost = hostname.toLowerCase().split(":")[0] ?? ""
  if (!normalizedHost) {
    return headerFallback ?? "dev"
  }

  if (normalizedHost === "localhost" || normalizedHost.endsWith(".localhost")) {
    return headerFallback ?? "dev"
  }

  const hostParts = normalizedHost.split(".")
  if (hostParts.length >= 3) {
    return hostParts[0] ?? "dev"
  }
  return headerFallback ?? "dev"
}

type AuthenticatedRequest = NextRequest & {
  auth: Session | null
}

export default auth(async function middleware(request: AuthenticatedRequest) {
  const pathname = request.nextUrl.pathname
  const requestHeaders = new Headers(request.headers)
  const isE2EBypass =
    process.env.NODE_ENV !== "production" &&
    request.headers.get("x-e2e-auth-bypass") === "true"
  const tenantSlug = extractTenantSlug(
    request.headers.get("host") ?? "",
    request.headers.get("x-tenant-slug"),
  )
  requestHeaders.set("x-tenant-slug", tenantSlug)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  const nextResponse = () =>
    applySecurityHeaders(
      NextResponse.next({ request: { headers: requestHeaders } }),
      apiUrl,
    )

  if (isStaticAsset(pathname) || isPublicPath(pathname)) {
    return nextResponse()
  }

  if (isE2EBypass) {
    return nextResponse()
  }

  const session = request.auth

  if (!session?.user) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set(
      "callbackUrl",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    )
    return applySecurityHeaders(NextResponse.redirect(loginUrl), apiUrl)
  }

  const orgSetupComplete =
    typeof session.user.org_setup_complete === "boolean"
      ? session.user.org_setup_complete
      : true
  if (!orgSetupComplete) {
    const isOrgSetupPath =
      pathname === ORG_SETUP_PATH ||
      pathname.startsWith(`${ORG_SETUP_PATH}/`) ||
      pathname === ORG_SETUP_COA_PATH ||
      pathname.startsWith(`${ORG_SETUP_COA_PATH}/`) ||
      pathname === ORGS_PATH
    if (!isOrgSetupPath) {
      const setupUrl = new URL(ORG_SETUP_PATH, request.url)
      setupUrl.searchParams.set(
        "next",
        `${request.nextUrl.pathname}${request.nextUrl.search}`,
      )
      return applySecurityHeaders(NextResponse.redirect(setupUrl), apiUrl)
    }
  } else if (
    pathname === ORG_SETUP_PATH ||
    pathname.startsWith(`${ORG_SETUP_PATH}/`) ||
    pathname === ORG_SETUP_COA_PATH ||
    pathname.startsWith(`${ORG_SETUP_COA_PATH}/`)
  ) {
    const next = request.nextUrl.searchParams.get("next")
    const destination = next && next.startsWith("/") ? next : "/dashboard"
    return applySecurityHeaders(
      NextResponse.redirect(new URL(destination, request.url)),
      apiUrl,
    )
  }

  if (
    request.nextUrl.pathname.startsWith("/admin") ||
    request.nextUrl.pathname.startsWith("/control-plane")
  ) {
    const role = String(session.user.role ?? "")
    if (!["platform_owner", "platform_admin", "super_admin", "admin"].includes(role)) {
      return applySecurityHeaders(
        NextResponse.redirect(new URL("/dashboard", request.url)),
        apiUrl,
      )
    }
  }
  if (request.nextUrl.pathname.startsWith("/trust")) {
    const role = String(session.user.role ?? "")
    if (role !== "finance_leader") {
      return applySecurityHeaders(
        NextResponse.redirect(new URL("/dashboard", request.url)),
        apiUrl,
      )
    }
  }

  return nextResponse()
})

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
