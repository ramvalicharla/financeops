"use client"

import { useCallback, useEffect, useRef, useState } from "react"

const normalizeError = (error: unknown): Error =>
  error instanceof Error ? error : new Error("Something went wrong.")

/**
 * Wraps an async action with loading, error, and reset state.
 *
 * @param actionFn Async function to execute.
 * @returns An executor plus loading/error/reset state for the current action.
 */
export function useAsyncAction<Args extends unknown[], T>(
  actionFn: (...args: Args) => Promise<T>,
) {
  const actionRef = useRef(actionFn)
  const mountedRef = useRef(true)
  const inFlightRef = useRef<Promise<T> | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    actionRef.current = actionFn
  }, [actionFn])

  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const reset = useCallback(() => {
    if (!mountedRef.current) {
      return
    }
    setError(null)
  }, [])

  const execute = useCallback(
    async (...args: Args): Promise<T> => {
      if (inFlightRef.current) {
        return inFlightRef.current
      }

      setIsLoading(true)
      setError(null)

      const promise = actionRef.current(...args)
      inFlightRef.current = promise

      try {
        return await promise
      } catch (error) {
        const normalizedError = normalizeError(error)
        if (mountedRef.current) {
          setError(normalizedError)
        }
        throw normalizedError
      } finally {
        inFlightRef.current = null
        if (mountedRef.current) {
          setIsLoading(false)
        }
      }
    },
    [],
  )

  return { execute, isLoading, error, reset }
}
