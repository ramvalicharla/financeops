import * as Sentry from "@sentry/nextjs"

import { buildSentryOptions } from "./sentry.shared"

if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init(buildSentryOptions())
}
