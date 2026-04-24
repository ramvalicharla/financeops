import { describe, expect, it, vi } from "vitest"
import { listUserOrgs } from "@/lib/api/orgs"

const getMock = vi.fn()

vi.mock("@/lib/api/client", () => ({
  default: {
    get: (...args: unknown[]) => getMock(...args),
  },
}))

describe("listUserOrgs", () => {
  it("maps user tenant payload into org summaries", async () => {
    getMock.mockResolvedValue({
      data: [
        {
          id: "tenant-1",
          slug: "acme-finance",
          name: "Acme Finance",
          role: "tenant_owner",
          status: "active",
          plan: "professional",
        },
      ],
    })

    await expect(listUserOrgs()).resolves.toEqual([
      {
        tenant_id: "tenant-1",
        tenant_slug: "acme-finance",
        display_name: "Acme Finance",
        entity_count: 0,
        last_active_at: null,
        subscription_tier: "pro",
        status: "active",
      },
    ])
    expect(getMock).toHaveBeenCalledWith("/api/v1/user/tenants")
  })
})
