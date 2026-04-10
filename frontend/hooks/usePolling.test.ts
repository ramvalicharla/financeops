import { renderHook, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { usePolling } from "./usePolling"

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("returns isPolling true when enabled", () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fetchFn, 1000, true))
    expect(result.current.isPolling).toBe(true)
  })

  it("returns isPolling false when disabled", () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fetchFn, 1000, false))
    expect(result.current.isPolling).toBe(false)
  })

  it("does not call fetchFn immediately on mount (interval-based)", () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling(fetchFn, 1000, true))
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it("calls fetchFn after one interval", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling(fetchFn, 1000, true))

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })

    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it("calls fetchFn multiple times across multiple intervals", async () => {
    // Use a synchronously-resolving mock so inFlightRef clears before next tick
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling(fetchFn, 1000, true))

    // Advance one interval at a time, flushing promises between each
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })

    expect(fetchFn).toHaveBeenCalledTimes(3)
  })

  it("stops calling fetchFn after unmount", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { unmount } = renderHook(() => usePolling(fetchFn, 1000, true))

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(fetchFn).toHaveBeenCalledTimes(1)

    unmount()

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it("stops polling when enabled changes to false", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    let enabled = true
    const { rerender, result } = renderHook(() => usePolling(fetchFn, 1000, enabled))

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(fetchFn).toHaveBeenCalledTimes(1)

    enabled = false
    rerender()
    expect(result.current.isPolling).toBe(false)

    await act(async () => {
      vi.advanceTimersByTime(3000)
    })
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it("resumes polling when enabled changes back to true", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    let enabled = false
    const { rerender } = renderHook(() => usePolling(fetchFn, 1000, enabled))

    await act(async () => {
      vi.advanceTimersByTime(2000)
    })
    expect(fetchFn).not.toHaveBeenCalled()

    enabled = true
    rerender()

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it("does not call fetchFn if enabled is false from the start", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling(fetchFn, 500, false))

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(fetchFn).not.toHaveBeenCalled()
  })

  it("stops polling after reaching the maximum attempts", async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const onMaxAttemptsReached = vi.fn()
    renderHook(() =>
      usePolling(fetchFn, 1000, true, { maxAttempts: 3, onMaxAttemptsReached }),
    )

    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(5000)
      await Promise.resolve()
    })

    expect(fetchFn).toHaveBeenCalledTimes(3)
    expect(onMaxAttemptsReached).toHaveBeenCalledTimes(1)
  })
})
