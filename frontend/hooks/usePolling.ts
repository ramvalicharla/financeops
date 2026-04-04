"use client"

import { useEffect, useRef, useState } from "react"

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
) {
  const fetchRef = useRef(fetchFn)
  const inFlightRef = useRef(false)
  const [isPolling, setIsPolling] = useState(enabled)

  useEffect(() => {
    fetchRef.current = fetchFn
  }, [fetchFn])

  useEffect(() => {
    if (!enabled) {
      setIsPolling(false)
      return
    }

    setIsPolling(true)

    const intervalId = window.setInterval(() => {
      if (inFlightRef.current) {
        return
      }

      inFlightRef.current = true
      void fetchRef.current().finally(() => {
        inFlightRef.current = false
      })
    }, intervalMs)

    return () => {
      window.clearInterval(intervalId)
      inFlightRef.current = false
      setIsPolling(false)
    }
  }, [enabled, intervalMs])

  return { isPolling }
}
