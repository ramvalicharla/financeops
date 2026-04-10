"use client"

import { useEffect, useRef, useState } from "react"

const DEFAULT_MAX_POLL_ATTEMPTS = 60

type UsePollingOptions = {
  maxAttempts?: number
  onMaxAttemptsReached?: () => void
}

/**
 * Repeatedly invokes an async fetch function while polling is enabled.
 *
 * @param fetchFn Async callback to run on each polling interval.
 * @param intervalMs Polling interval in milliseconds.
 * @param enabled Whether polling should currently be active.
 * @returns Polling state so consumers can reflect when the interval is active.
 */
export function usePolling(
  fetchFn: () => Promise<void>,
  intervalMs: number,
  enabled: boolean,
  options?: UsePollingOptions,
) {
  const fetchRef = useRef(fetchFn)
  const inFlightRef = useRef(false)
  const attemptsRef = useRef(0)
  const limitReachedRef = useRef(false)
  const [isPolling, setIsPolling] = useState(enabled)
  const maxAttempts = options?.maxAttempts ?? DEFAULT_MAX_POLL_ATTEMPTS

  useEffect(() => {
    fetchRef.current = fetchFn
  }, [fetchFn])

  useEffect(() => {
    attemptsRef.current = 0
    limitReachedRef.current = false

    if (!enabled) {
      setIsPolling(false)
      return
    }

    setIsPolling(true)

    const intervalId = window.setInterval(() => {
      if (inFlightRef.current) {
        return
      }
      if (attemptsRef.current >= maxAttempts) {
        if (!limitReachedRef.current) {
          limitReachedRef.current = true
          setIsPolling(false)
          options?.onMaxAttemptsReached?.()
        }
        window.clearInterval(intervalId)
        return
      }

      inFlightRef.current = true
      attemptsRef.current += 1
      void fetchRef.current().finally(() => {
        inFlightRef.current = false
      })
    }, intervalMs)

    return () => {
      window.clearInterval(intervalId)
      inFlightRef.current = false
      setIsPolling(false)
    }
  }, [enabled, intervalMs, maxAttempts, options])

  return { isPolling }
}
