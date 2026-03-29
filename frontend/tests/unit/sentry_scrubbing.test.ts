import { describe, expect, it } from "vitest"

import { scrubSentryEvent } from "../../sentry.client.config"

describe("sentry scrubbing", () => {
  it("beforeSend removes Authorization header from Sentry events.", () => {
    const event = {
      request: {
        headers: {
          authorization: "Bearer secret-token",
        },
      },
    }

    const result = scrubSentryEvent(event)
    expect((result.request?.headers as Record<string, unknown>)?.authorization).toBeUndefined()
    expect(JSON.stringify(result)).not.toContain("secret-token")
  })

  it("beforeSend removes Cookie header.", () => {
    const event = {
      request: {
        headers: {
          cookie: "session=abc123",
        },
      },
    }

    const result = scrubSentryEvent(event)
    expect((result.request?.headers as Record<string, unknown>)?.cookie).toBeUndefined()
  })

  it("beforeSend removes user.email.", () => {
    const event = {
      user: {
        email: "user@example.com",
      },
    }

    const result = scrubSentryEvent(event)
    expect(result.user?.email).toBeUndefined()
    expect(JSON.stringify(result)).not.toContain("example.com")
  })
})
