import { renderHook, act, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { useAsyncAction } from "./useAsyncAction"

describe("useAsyncAction", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("starts with isLoading false", () => {
    const actionFn = vi.fn().mockResolvedValue("result")
    const { result } = renderHook(() => useAsyncAction(actionFn))
    expect(result.current.isLoading).toBe(false)
  })

  it("starts with error null", () => {
    const actionFn = vi.fn().mockResolvedValue("result")
    const { result } = renderHook(() => useAsyncAction(actionFn))
    expect(result.current.error).toBeNull()
  })

  it("sets isLoading true during execution", async () => {
    let resolveAction!: (v: string) => void
    const promise = new Promise<string>((res) => {
      resolveAction = res
    })
    const actionFn = vi.fn().mockReturnValue(promise)
    const { result } = renderHook(() => useAsyncAction(actionFn))

    act(() => {
      void result.current.execute()
    })

    expect(result.current.isLoading).toBe(true)

    await act(async () => {
      resolveAction("done")
      await promise
    })

    expect(result.current.isLoading).toBe(false)
  })

  it("returns the resolved value from execute", async () => {
    const actionFn = vi.fn().mockResolvedValue("success-value")
    const { result } = renderHook(() => useAsyncAction(actionFn))

    let returned: string | undefined
    await act(async () => {
      returned = await result.current.execute()
    })

    expect(returned).toBe("success-value")
  })

  it("sets error on failure", async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error("action failed"))
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      try {
        await result.current.execute()
      } catch {
        // expected
      }
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error?.message).toBe("action failed")
    expect(result.current.isLoading).toBe(false)
  })

  it("wraps non-Error rejections in an Error", async () => {
    const actionFn = vi.fn().mockRejectedValue("plain string")
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      try {
        await result.current.execute()
      } catch {
        // expected
      }
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error?.message).toBe("Something went wrong.")
  })

  it("rethrows the error from execute", async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error("boom"))
    const { result } = renderHook(() => useAsyncAction(actionFn))

    let caught: Error | undefined
    await act(async () => {
      try {
        await result.current.execute()
      } catch (e) {
        caught = e as Error
      }
    })

    expect(caught).toBeInstanceOf(Error)
    expect(caught?.message).toBe("boom")
  })

  it("reset() clears error back to null", async () => {
    const actionFn = vi.fn().mockRejectedValue(new Error("fail"))
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      try {
        await result.current.execute()
      } catch {
        // expected
      }
    })

    expect(result.current.error).not.toBeNull()

    act(() => {
      result.current.reset()
    })

    expect(result.current.error).toBeNull()
  })

  it("passes arguments through to actionFn", async () => {
    const actionFn = vi.fn().mockResolvedValue("ok")
    const { result } = renderHook(() => useAsyncAction(actionFn))

    await act(async () => {
      await result.current.execute("arg1", 42, true)
    })

    expect(actionFn).toHaveBeenCalledWith("arg1", 42, true)
  })

  it("deduplicates concurrent calls — returns same promise", async () => {
    let callCount = 0
    const actionFn = vi.fn().mockImplementation(
      () =>
        new Promise<string>((res) => {
          callCount++
          setTimeout(() => res("done"), 100)
        }),
    )

    const { result } = renderHook(() => useAsyncAction(actionFn))

    let p1: Promise<string>, p2: Promise<string>
    act(() => {
      p1 = result.current.execute()
      p2 = result.current.execute()
    })

    await act(async () => {
      await Promise.all([p1!, p2!])
    })

    expect(callCount).toBe(1)
  })
})
