import { describe, expect, it } from "vitest"

import { queryRetryDelay, shouldRetryQuery } from "../../lib/query-client"

describe("query retry policy", () => {
  it("401 errors are not retried - auth failure is intentional.", () => {
    const error = { response: { status: 401 } }
    expect(shouldRetryQuery(0, error)).toBe(false)
  })

  it("Network errors are retried up to 2 times.", () => {
    const error = {}
    expect(shouldRetryQuery(0, error)).toBe(true)
    expect(shouldRetryQuery(1, error)).toBe(true)
    expect(shouldRetryQuery(2, error)).toBe(false)
  })

  it("Server errors are retried.", () => {
    const error = { response: { status: 500 } }
    expect(shouldRetryQuery(0, error)).toBe(true)
    expect(shouldRetryQuery(2, error)).toBe(false)
  })

  it("Retry delay never exceeds 10,000ms.", () => {
    expect(queryRetryDelay(0)).toBe(1000)
    expect(queryRetryDelay(1)).toBe(2000)
    expect(queryRetryDelay(2)).toBe(4000)
    expect(queryRetryDelay(10)).toBe(10000)
  })
})
