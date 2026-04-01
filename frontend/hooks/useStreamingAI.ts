"use client"

import { useState } from "react"
import { getSession } from "next-auth/react"
import { BASE_URL } from "@/lib/api/client"

type StreamPayload = {
  chunk?: string
  done?: boolean
  error?: string
}

const parseSSEChunks = (buffer: string): {
  events: StreamPayload[]
  remainder: string
} => {
  const events: StreamPayload[] = []
  let remainder = buffer

  while (true) {
    const delimiterIndex = remainder.indexOf("\n\n")
    if (delimiterIndex === -1) {
      break
    }

    const rawEvent = remainder.slice(0, delimiterIndex)
    remainder = remainder.slice(delimiterIndex + 2)

    for (const line of rawEvent.split("\n")) {
      if (!line.startsWith("data: ")) {
        continue
      }
      const jsonText = line.slice(6).trim()
      if (!jsonText) {
        continue
      }
      try {
        events.push(JSON.parse(jsonText) as StreamPayload)
      } catch {
        events.push({ error: "Malformed streaming payload" })
      }
    }
  }

  return { events, remainder }
}

export function useStreamingAI() {
  const [response, setResponse] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [traceId, setTraceId] = useState<string | null>(null)

  const stream = async (prompt: string, systemPrompt?: string): Promise<void> => {
    setResponse("")
    setError(null)
    setTraceId(null)
    setIsStreaming(true)

    try {
      if (!BASE_URL) {
        throw new Error("NEXT_PUBLIC_API_URL is required")
      }
      const endpoint = `${BASE_URL}/api/v1/ai/stream`
      const session = await getSession()
      const accessToken = session?.access_token
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      }
      if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`
      }
      const res = await fetch(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prompt,
          system_prompt: systemPrompt ?? "",
        }),
      })

      const traceHeader = res.headers.get("X-AI-Trace-ID")
      if (traceHeader) {
        setTraceId(traceHeader)
      }

      if (!res.ok || !res.body) {
        setError("Unable to stream AI response")
        setIsStreaming(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffered = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }

        buffered += decoder.decode(value, { stream: true })
        const parsed = parseSSEChunks(buffered)
        buffered = parsed.remainder

        for (const event of parsed.events) {
          if (event.error) {
            setError(event.error)
            setIsStreaming(false)
            return
          }
          if (event.chunk) {
            setResponse((prev) => prev + event.chunk)
          }
          if (event.done) {
            setIsStreaming(false)
            return
          }
        }
      }
    } catch {
      setError("Unable to stream AI response")
    } finally {
      setIsStreaming(false)
    }
  }

  return { response, isStreaming, error, traceId, stream }
}
