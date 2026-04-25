import { describe, it, expect } from "vitest"
import {
  getModuleIcon,
  MODULE_ICON_MAP,
  FALLBACK_MODULE_ICON,
} from "../module-icons"
import {
  LayoutDashboard,
  Plug,
  BookOpen,
  Scale,
  CalendarCheck,
  FileBarChart,
  Settings,
  CircleDot,
} from "lucide-react"

describe("MODULE_ICON_MAP", () => {
  it("covers exactly the 7 backend workspace_keys from _WORKSPACE_DEFINITIONS", () => {
    const expectedKeys = [
      "dashboard",
      "erp",
      "accounting",
      "reconciliation",
      "close",
      "reports",
      "settings",
    ]
    expect(Object.keys(MODULE_ICON_MAP).sort()).toEqual(expectedKeys.sort())
  })
})

describe("getModuleIcon", () => {
  it.each([
    ["dashboard", LayoutDashboard],
    ["erp", Plug],
    ["accounting", BookOpen],
    ["reconciliation", Scale],
    ["close", CalendarCheck],
    ["reports", FileBarChart],
    ["settings", Settings],
  ] as const)("returns correct icon for key '%s'", (key, expected) => {
    expect(getModuleIcon(key)).toBe(expected)
  })

  it("returns FALLBACK_MODULE_ICON for undefined", () => {
    expect(getModuleIcon(undefined)).toBe(FALLBACK_MODULE_ICON)
    expect(getModuleIcon(undefined)).toBe(CircleDot)
  })

  it("returns FALLBACK_MODULE_ICON for null", () => {
    expect(getModuleIcon(null)).toBe(FALLBACK_MODULE_ICON)
  })

  it("returns FALLBACK_MODULE_ICON for unknown key", () => {
    expect(getModuleIcon("nonexistent_workspace")).toBe(FALLBACK_MODULE_ICON)
  })

  it("is case-insensitive (returns BookOpen for 'ACCOUNTING')", () => {
    expect(getModuleIcon("ACCOUNTING")).toBe(BookOpen)
  })

  it.each([
    "overview",
    "financials",
    "far",
    "consolidation",
    "lease",
    "banking",
    "tax",
    "budgeting",
    "mis",
  ])("regression guard: old draft key '%s' returns FALLBACK_MODULE_ICON", (oldKey) => {
    expect(getModuleIcon(oldKey)).toBe(FALLBACK_MODULE_ICON)
  })
})
