import { render, act, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import type { Mock } from "vitest"
import { SidebarCollapseBootstrap } from "../SidebarCollapseBootstrap"

// ── API mock ─────────────────────────────────────────────────────────────────

vi.mock("@/lib/api/userPreferences", () => ({
  getUserPreferences: vi.fn(),
  updateUserPreferences: vi.fn(),
}))

// ── Store mock ────────────────────────────────────────────────────────────────

vi.mock("@/lib/store/workspace", () => ({
  useWorkspaceStore: vi.fn(),
}))

import { useWorkspaceStore } from "@/lib/store/workspace"
import { getUserPreferences, updateUserPreferences } from "@/lib/api/userPreferences"

// ── Helpers ───────────────────────────────────────────────────────────────────

function mockWorkspace({
  sidebarCollapsed = false,
  setSidebarCollapsed = vi.fn(),
}: {
  sidebarCollapsed?: boolean
  setSidebarCollapsed?: Mock
} = {}) {
  // Zustand getState() is accessed directly in the component (not through React hooks)
  // so we need to mock the module-level getState too.
  const storeState = { sidebarCollapsed, setSidebarCollapsed }
  ;(useWorkspaceStore as unknown as Mock).mockImplementation(
    (selector?: (s: typeof storeState) => unknown) =>
      selector ? selector(storeState) : storeState,
  )
  // Mock getState() used in the catch/then branches
  ;(useWorkspaceStore as { getState: () => unknown }).getState = () => storeState
  return storeState
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SidebarCollapseBootstrap", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    ;(updateUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: false })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("does not call setSidebarCollapsed when server returns null", async () => {
    const { setSidebarCollapsed } = mockWorkspace({ sidebarCollapsed: false })
    ;(getUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: null })

    render(<SidebarCollapseBootstrap />)
    await act(async () => { await vi.runAllTimersAsync() })

    expect(getUserPreferences).toHaveBeenCalledOnce()
    expect(setSidebarCollapsed).not.toHaveBeenCalled()
  })

  it("calls setSidebarCollapsed with server value when server returns non-null", async () => {
    const { setSidebarCollapsed } = mockWorkspace({ sidebarCollapsed: false })
    ;(getUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: true })

    render(<SidebarCollapseBootstrap />)
    await act(async () => { await vi.runAllTimersAsync() })

    expect(setSidebarCollapsed).toHaveBeenCalledWith(true)
  })

  it("server value overrides a differing localStorage value", async () => {
    // localStorage has false, server has true — server wins
    const { setSidebarCollapsed } = mockWorkspace({ sidebarCollapsed: false })
    ;(getUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: true })

    render(<SidebarCollapseBootstrap />)
    await act(async () => { await vi.runAllTimersAsync() })

    expect(setSidebarCollapsed).toHaveBeenCalledWith(true)
  })

  it("fires updateUserPreferences (debounced) when sidebarCollapsed changes after bootstrap", async () => {
    ;(getUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: null })

    // Start with collapsed=false, bootstrap resolves, then value changes to true
    const setSidebarCollapsed = vi.fn()
    let storedCollapsed = false
    ;(useWorkspaceStore as unknown as Mock).mockImplementation(
      (selector?: (s: { sidebarCollapsed: boolean; setSidebarCollapsed: Mock }) => unknown) => {
        const state = { sidebarCollapsed: storedCollapsed, setSidebarCollapsed }
        return selector ? selector(state) : state
      },
    )
    ;(useWorkspaceStore as { getState: () => unknown }).getState = () => ({
      sidebarCollapsed: storedCollapsed,
      setSidebarCollapsed,
    })

    const { rerender } = render(<SidebarCollapseBootstrap />)
    // Bootstrap resolves
    await act(async () => { await vi.runAllTimersAsync() })

    // Simulate toggle: localStorage changes to true
    storedCollapsed = true
    rerender(<SidebarCollapseBootstrap />)

    // Debounce timer fires
    await act(async () => { vi.advanceTimersByTime(300) })

    expect(updateUserPreferences).toHaveBeenCalledWith({ sidebar_collapsed: true })
  })

  it("API failure on toggle leaves no user-visible error; logs console warning", async () => {
    ;(getUserPreferences as Mock).mockResolvedValue({ sidebar_collapsed: null })
    ;(updateUserPreferences as Mock).mockRejectedValue(new Error("Network error"))

    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {})

    let storedCollapsed = false
    ;(useWorkspaceStore as unknown as Mock).mockImplementation(
      (selector?: (s: { sidebarCollapsed: boolean; setSidebarCollapsed: Mock }) => unknown) => {
        const state = { sidebarCollapsed: storedCollapsed, setSidebarCollapsed: vi.fn() }
        return selector ? selector(state) : state
      },
    )
    ;(useWorkspaceStore as { getState: () => unknown }).getState = () => ({
      sidebarCollapsed: storedCollapsed,
      setSidebarCollapsed: vi.fn(),
    })

    const { rerender } = render(<SidebarCollapseBootstrap />)
    await act(async () => { await vi.runAllTimersAsync() })

    storedCollapsed = true
    rerender(<SidebarCollapseBootstrap />)
    await act(async () => {
      vi.advanceTimersByTime(300)
      await vi.runAllTimersAsync()
    })

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("[SidebarCollapseBootstrap]"),
    )
    warnSpy.mockRestore()
  })
})
