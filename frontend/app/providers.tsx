"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { SessionProvider } from "next-auth/react"
import { ThemeProvider } from "next-themes"
import { useState } from "react"
import { queryRetryDelay, shouldRetryQuery } from "@/lib/query-client"
import { TooltipProvider } from "@/components/ui/tooltip"

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
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={300}>
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            {children}
          </ThemeProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </SessionProvider>
  )
}
