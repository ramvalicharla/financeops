import { renderHook, waitFor, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { useFetch } from "./useFetch"

describe("useFetch", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("starts with isLoading true", () => {
    const fetchFn = vi.fn().mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useFetch(fetchFn, []))
    expect(result.current.isLoading).toBe(true)
  })

  it("starts with data undefined", () => {
    const fetchFn = vi.fn().mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useFetch(fetchFn, []))
    expect(result.current.data).toBeUndefined()
  })

  it("starts with error null", () => {
    const fetchFn = vi.fn().mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useFetch(fetchFn, []))
    expect(result.current.error).toBeNull()
  })

  it("sets data and clears loading on successful fetch", async () => {
    const fetchFn = vi.fn().mockResolvedValue({ id: 1, name: "test" })
    const { result } = renderHook(() => useFetch(fetchFn, []))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.data).toEqual({ id: 1, name: "test" })
    expect(result.current.error).toBeNull()
  })

  it("sets error and clears loading on failed fetch", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error("Network error"))
    const { result } = renderHook(() => useFetch(fetchFn, []))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error?.message).toBe("Network error")
    expect(result.current.data).toBeUndefined()
  })

  it("wraps non-Error rejections in an Error", async () => {
    const fetchFn = vi.fn().mockRejectedValue("string error")
    const { result } = renderHook(() => useFetch(fetchFn, []))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error?.message).toBe("Something went wrong.")
  })

  it("refetch triggers a new fetch and updates data", async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce("first")
      .mockResolvedValueOnce("second")

    const { result } = renderHook(() => useFetch(fetchFn, []))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data).toBe("first")

    await act(async () => {
      await result.current.refetch()
    })

    expect(result.current.data).toBe("second")
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })

  it("refetch sets isLoading true then false", async () => {
    let resolveSecond!: (v: string) => void
    const secondPromise = new Promise<string>((res) => {
      resolveSecond = res
    })

    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce("first")
      .mockReturnValueOnce(secondPromise)

    const { result } = renderHook(() => useFetch(fetchFn, []))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      void result.current.refetch()
    })

    expect(result.current.isLoading).toBe(true)

    await act(async () => {
      resolveSecond("second")
      await secondPromise
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
  })

  it("refetches when deps change", async () => {
    const fetchFn = vi.fn().mockResolvedValue("data")
    let dep = 1
    const { rerender } = renderHook(() => useFetch(fetchFn, [dep]))

    await waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1))

    dep = 2
    rerender()

    await waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(2))
  })

  it("does not update state after unmount", async () => {
    let resolve!: (v: string) => void
    const promise = new Promise<string>((res) => {
      resolve = res
    })
    const fetchFn = vi.fn().mockReturnValue(promise)

    const { result, unmount } = renderHook(() => useFetch(fetchFn, []))

    unmount()

    // Should not throw
    await act(async () => {
      resolve("late data")
      await promise
    })

    // After unmount, data was never set (mountedRef guards it)
    expect(result.current.data).toBeUndefined()
  })
})
