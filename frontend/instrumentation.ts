import * as Sentry from "@sentry/nextjs"

import { buildSentryOptions } from "./sentry.shared"

export async function register() {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
    return
  }

  if (process.env.NEXT_RUNTIME === "nodejs" || process.env.NEXT_RUNTIME === "edge") {
    Sentry.init(buildSentryOptions())
  }
}
