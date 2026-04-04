"use client"

import { useCallback, useEffect, useRef, useState } from "react"

const normalizeError = (error: unknown): Error =>
  error instanceof Error ? error : new Error("Something went wrong.")

/**
 * Fetches async data on mount and whenever the provided dependencies change.
 *
 * @param fetchFn Async fetcher that resolves the next data value.
 * @param deps Dependency list that triggers automatic refetching.
 * @returns The latest data, loading/error state, and a manual refetch function.
 */
export function useFetch<T>(fetchFn: () => Promise<T>, deps: unknown[]) {
  const fetchRef = useRef(fetchFn)
  const mountedRef = useRef(true)
  const requestIdRef = useRef(0)
  const [data, setData] = useState<T | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    fetchRef.current = fetchFn
  }, [fetchFn])

  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refetch = useCallback(async (): Promise<T | undefined> => {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchRef.current()
      if (mountedRef.current && requestIdRef.current === requestId) {
        setData(result)
      }
      return result
    } catch (error) {
      const normalizedError = normalizeError(error)
      if (mountedRef.current && requestIdRef.current === requestId) {
        setError(normalizedError)
      }
      return undefined
    } finally {
      if (mountedRef.current && requestIdRef.current === requestId) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    void refetch()
  }, [refetch, ...deps])

  return { data, isLoading, error, refetch }
}
