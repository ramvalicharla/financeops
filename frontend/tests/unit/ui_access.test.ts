import { describe, expect, it } from "vitest"

import {
  canAccessModule,
  canPerformAction,
  filterNavigationItems,
  getAccessErrorMessage,
} from "../../lib/ui-access"
import type { BillingEntitlement } from "../../types/billing"

const entitlements: BillingEntitlement[] = [
  {
    id: "ent-1",
    feature_name: "erp_integration",
    access_type: "boolean",
    effective_limit: null,
    source: "plan",
    source_reference_id: null,
    metadata: {},
  },
]

describe("ui access helpers", () => {
  it("allows module access when the entitlement exists", () => {
    expect(canAccessModule("erp_integration", entitlements)).toBe(true)
    expect(canAccessModule("mis_manager", entitlements)).toBe(false)
  })

  it("limits owner-only actions to platform owners", () => {
    expect(canPerformAction("platform.users.manage", "platform_owner")).toBe(true)
    expect(canPerformAction("platform.users.manage", "platform_admin")).toBe(false)
  })

  it("filters entitlement-gated navigation items", () => {
    const items = filterNavigationItems(
      [
        { label: "ERP Connectors", href: "/erp/connectors", icon: (() => null) as never },
        { label: "MIS", href: "/mis", icon: (() => null) as never },
      ],
      "finance_leader",
      entitlements,
      true,
    )

    expect(items).toHaveLength(1)
    expect("href" in items[0] ? items[0].href : "").toBe("/erp/connectors")
  })

  it("maps entitlement denials to a clear user message", () => {
    expect(
      getAccessErrorMessage(
        {
          response: { status: 403 },
          payload: {
            code: "entitlement_not_configured",
            message: "entitlement_not_configured",
          },
        },
        "MIS",
      ),
    ).toBe("MIS is not enabled for your organization.")
  })
})
