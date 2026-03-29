import { describe, expect, it } from "vitest"

import { AnomalySchema } from "../../lib/schemas/anomaly"
import { CreditBalanceSchema } from "../../lib/schemas/credit"
import { MISDashboardSchema } from "../../lib/schemas/mis"

describe("zod runtime validation", () => {
  it("MIS dashboard schema rejects numeric (float) financial values.", () => {
    const invalidData = {
      period: "2025-03",
      entities: [
        {
          entity_id: crypto.randomUUID(),
          entity_name: "Test",
          lines: [
            {
              line_item: "Revenue",
              current_value: 1234567,
              previous_value: "1200000",
              variance: "34567",
            },
          ],
        },
      ],
    }
    expect(() => MISDashboardSchema.parse(invalidData)).toThrow()
  })

  it("MIS dashboard schema accepts financial amounts as strings.", () => {
    const validData = {
      period: "2025-03",
      entities: [
        {
          entity_id: crypto.randomUUID(),
          entity_name: "Test",
          lines: [
            {
              line_item: "Revenue",
              current_value: "1234567.00",
              previous_value: "1200000.00",
              variance: "34567.00",
            },
          ],
        },
      ],
    }
    expect(() => MISDashboardSchema.parse(validData)).not.toThrow()
  })

  it("Credit balance schema rejects numeric values - must be strings.", () => {
    expect(() =>
      CreditBalanceSchema.parse({
        balance: 100,
        reserved: "0",
        available: "100",
        currency: "USD",
      }),
    ).toThrow()
  })

  it("Anomaly schema rejects unknown severity values.", () => {
    expect(() =>
      AnomalySchema.parse({
        id: crypto.randomUUID(),
        severity: "ultra-critical",
        category: "test",
        status: "open",
        detected_at: new Date().toISOString(),
      }),
    ).toThrow()
  })
})
