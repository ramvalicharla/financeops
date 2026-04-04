"use client"

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react"
import { Loader2, Search, Sparkles } from "lucide-react"
import { useRouter } from "next/navigation"
import { searchGlobal } from "@/lib/api/search"
import type { SearchResultRow } from "@/lib/types/search"
import { SearchResult } from "@/components/search/SearchResult"
import { Dialog } from "@/components/ui/Dialog"
import { Input } from "@/components/ui/input"
import { useStreamingAI } from "@/hooks/useStreamingAI"

type CommandPaletteProps = {
  isOpen: boolean
  onClose: () => void
}

const groupLabel = (entityType: string): string => entityType.replaceAll("_", " ")

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const aiInputRef = useRef<HTMLInputElement | null>(null)
  const [mode, setMode] = useState<"search" | "ai">("search")
  const [query, setQuery] = useState("")
  const [aiPrompt, setAiPrompt] = useState("")
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResultRow[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const {
    response: aiResponse,
    isStreaming,
    error: streamError,
    traceId,
    stream,
  } = useStreamingAI()

  useEffect(() => {
    if (!isOpen) {
      return
    }
    const timer = setTimeout(() => {
      if (mode === "search") {
        inputRef.current?.focus()
      } else {
        aiInputRef.current?.focus()
      }
    }, 10)
    return () => clearTimeout(timer)
  }, [isOpen, mode])

  useEffect(() => {
    if (!isOpen) {
      return
    }
    if (mode !== "search") {
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const payload = await searchGlobal({
          q: query,
          limit: 12,
        })
        setResults(payload)
        setSelectedIndex(0)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 200)
    return () => clearTimeout(timer)
  }, [isOpen, mode, query])

  const grouped = useMemo(() => {
    const bucket: Record<string, SearchResultRow[]> = {}
    for (const row of results) {
      if (!bucket[row.entity_type]) {
        bucket[row.entity_type] = []
      }
      bucket[row.entity_type].push(row)
    }
    return Object.entries(bucket)
  }, [results])

  const handleSelect = (row: SearchResultRow) => {
    onClose()
    router.push(row.url)
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (mode !== "search") {
      return
    }
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setSelectedIndex((prev) => (results.length === 0 ? 0 : (prev + 1) % results.length))
      return
    }
    if (event.key === "ArrowUp") {
      event.preventDefault()
      setSelectedIndex((prev) =>
        results.length === 0 ? 0 : (prev - 1 + results.length) % results.length,
      )
      return
    }
    if (event.key === "Enter") {
      event.preventDefault()
      const target = results[selectedIndex]
      if (target) {
        handleSelect(target)
      }
      return
    }
    if (event.key === "Escape") {
      event.preventDefault()
      onClose()
    }
  }

  const handleAIPrompt = async (): Promise<void> => {
    const prompt = aiPrompt.trim()
    if (!prompt) {
      return
    }
    setAiPrompt("")
    await stream(
      prompt,
      "You are a financial assistant for FinanceOps. The user is a CA or CFO. Answer concisely with Indian financial context (GST, IndAS, MCA, RBI). Never give tax advice.",
    )
  }

  if (!isOpen) {
    return null
  }

  let runningIndex = -1

  return (
    <Dialog open={isOpen} onClose={onClose} title="Command palette" size="lg">
      <div
        className={`mx-auto max-h-[85vh] w-full overflow-hidden ${
          mode === "ai" ? "max-w-4xl" : "max-w-3xl"
        }`}
      >
        <div className="flex border-b border-border">
          <button
            type="button"
            className={`px-4 py-2 text-sm ${mode === "search" ? "text-foreground" : "text-muted-foreground"}`}
            onClick={() => setMode("search")}
          >
            Search
          </button>
          <button
            type="button"
            className={`px-4 py-2 text-sm ${mode === "ai" ? "text-foreground" : "text-muted-foreground"}`}
            onClick={() => setMode("ai")}
          >
            Ask AI
          </button>
        </div>

        {mode === "search" ? (
          <>
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleInputKeyDown}
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="Type to search across all modules"
              />
              {loading ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
            </div>

            <div className="max-h-[70vh] overflow-y-auto p-3">
              {results.length === 0 && !loading ? (
                <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Type to search across all modules
                </p>
              ) : null}

              <div className="space-y-4">
                {grouped.map(([entityType, items]) => (
                  <section key={entityType} className="space-y-2">
                    <p className="px-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      {groupLabel(entityType)}
                    </p>
                    <div className="space-y-1">
                      {items.map((item) => {
                        runningIndex += 1
                        const currentIndex = runningIndex
                        return (
                          <SearchResult
                            key={`${item.entity_type}-${item.entity_id}`}
                            result={item}
                            query={query}
                            isActive={currentIndex === selectedIndex}
                            onSelect={handleSelect}
                          />
                        )
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="p-4">
            <div className="rounded-md border border-border/60 bg-background p-3">
              <p className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                FinanceOps AI
              </p>
              <div className="min-h-[220px] whitespace-pre-wrap text-sm text-foreground">
                {aiResponse || "Ask anything about your financials..."}
                {isStreaming ? <span className="animate-pulse">▊</span> : null}
              </div>
              {streamError ? <p className="mt-2 text-xs text-red-400">{streamError}</p> : null}
              {traceId ? (
                <p className="mt-2 text-[10px] text-muted-foreground">Trace: {traceId}</p>
              ) : null}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Input
                ref={aiInputRef}
                placeholder="Ask anything about your financials..."
                value={aiPrompt}
                onChange={(event) => setAiPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    void handleAIPrompt()
                  }
                  if (event.key === "Escape") {
                    event.preventDefault()
                    onClose()
                  }
                }}
              />
              <button
                type="button"
                onClick={() => void handleAIPrompt()}
                className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
                disabled={isStreaming}
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  )
}
