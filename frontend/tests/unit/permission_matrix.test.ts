import { describe, expect, it } from "vitest"

import {
  ALL_PERMISSIONS,
  PERMISSIONS,
  PERMISSIONS_BY_MODULE,
  ROLE_ALIASES,
} from "../../lib/permission-matrix"

describe("permission matrix", () => {
  it("uses normalized permission keys", () => {
    for (const permission of ALL_PERMISSIONS) {
      expect(permission).toBe(permission.toLowerCase())
      expect(permission.includes(".")).toBe(true)
    }
  })

  it("has complete metadata for each permission", () => {
    for (const entry of Object.values(PERMISSIONS)) {
      expect(entry.module.length).toBeGreaterThan(0)
      expect(entry.roles.length).toBeGreaterThan(0)
      expect(Array.isArray(entry.entitlement_keys)).toBe(true)
    }
  })

  it("indexes permissions by module", () => {
    expect(PERMISSIONS_BY_MODULE.erp).toContain("erp.connectors.create")
    expect(PERMISSIONS_BY_MODULE.platform_users).toContain("platform.users.update")
  })

  it("maps canonical roles to runtime aliases", () => {
    expect(ROLE_ALIASES.tenant_owner).toContain("finance_leader")
    expect(ROLE_ALIASES.platform_owner).toContain("platform_owner")
  })
})
