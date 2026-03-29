"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { SessionProvider } from "next-auth/react"
import { useState } from "react"

type HttpLikeError = {
  response?: {
    status?: number
  }
}

export const shouldRetryQuery = (
  failureCount: number,
  error: unknown,
): boolean => {
  const status = (error as HttpLikeError)?.response?.status
  if (status && [401, 403, 404, 422].includes(status)) {
    return false
  }
  return failureCount < 2
}

export const queryRetryDelay = (attemptIndex: number): number =>
  Math.min(1000 * 2 ** attemptIndex, 10_000)

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            refetchOnWindowFocus: false,
            retry: shouldRetryQuery,
            retryDelay: queryRetryDelay,
          },
          mutations: {
            retry: false,
          },
        },
      }),
  )

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </SessionProvider>
  )
}
