import { describe, it, expect } from "vitest"
import { NAV_GROUPS } from "../nav-config"

describe("NAV_GROUPS", () => {
  it("contains exactly 3 groups", () => {
    expect(NAV_GROUPS).toHaveLength(3)
  })

  it("group ids are workspace, org, governance in that order", () => {
    expect(NAV_GROUPS.map((g) => g.id)).toEqual(["workspace", "org", "governance"])
  })

  it("workspace group contains exactly 4 items", () => {
    const workspace = NAV_GROUPS.find((g) => g.id === "workspace")
    expect(workspace?.items).toHaveLength(4)
  })

  it("org group contains exactly 5 items", () => {
    const org = NAV_GROUPS.find((g) => g.id === "org")
    expect(org?.items).toHaveLength(5)
  })

  it("governance group contains exactly 3 items", () => {
    const governance = NAV_GROUPS.find((g) => g.id === "governance")
    expect(governance?.items).toHaveLength(3)
  })

  it("no two items share the same id", () => {
    const allIds = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id))
    expect(new Set(allIds).size).toBe(allIds.length)
  })
})
