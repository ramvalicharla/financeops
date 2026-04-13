"use client"

import { useState } from "react"
import { ChevronLeft, Loader2, Sparkles } from "lucide-react"
import { useRouter } from "next/navigation"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { Input } from "@/components/ui/input"
import { useStreamingAI } from "@/hooks/useStreamingAI"
import {
  NAV_GROUP_DEFINITIONS,
  NAV_ITEMS,
  type NavigationLeafItem,
} from "@/lib/config/navigation"

// ---------------------------------------------------------------------------
// Static data — built once at module load from the nav config
// ---------------------------------------------------------------------------

const allNavLeafItems: NavigationLeafItem[] = Array.from(NAV_ITEMS).flatMap(
  (item): NavigationLeafItem[] =>
    "children" in item
      ? Array.from(item.children as readonly NavigationLeafItem[])
      : [item as NavigationLeafItem],
)

const hrefToNavItem = new Map<string, NavigationLeafItem>(
  allNavLeafItems.map((item) => [item.href, item]),
)

const QUICK_ACTIONS = [
  { label: "Run GL reconciliation", href: "/reconciliation/gl-tb" },
  { label: "Generate MIS report", href: "/mis" },
  { label: "Sync ERP data", href: "/erp/connectors" },
  { label: "View anomalies", href: "/anomalies" },
] as const

const AI_SYSTEM_PROMPT =
  "You are a financial assistant for Finqor. The user is a CA or CFO. Answer concisely with Indian financial context (GST, IndAS, MCA, RBI). Never give tax advice."

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type CommandPaletteProps = {
  isOpen: boolean
  onClose: () => void
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const router = useRouter()
  const [showAIPanel, setShowAIPanel] = useState(false)
  const [aiPrompt, setAiPrompt] = useState("")

  const { response: aiResponse, isStreaming, error: streamError, traceId, stream } =
    useStreamingAI()

  function handleClose() {
    setShowAIPanel(false)
    setAiPrompt("")
    onClose()
  }

  async function handleAISubmit(): Promise<void> {
    const prompt = aiPrompt.trim()
    if (!prompt) return
    setAiPrompt("")
    await stream(prompt, AI_SYSTEM_PROMPT)
  }

  return (
    <CommandDialog open={isOpen} onOpenChange={(open) => { if (!open) handleClose() }}>
      {!showAIPanel ? (
        <>
          <CommandInput placeholder="Search modules or type a command…" />
          <CommandList className="max-h-[min(400px,60vh)]">
            <CommandEmpty>No results found.</CommandEmpty>

            {NAV_GROUP_DEFINITIONS.map((group) => {
              const items = group.hrefs
                .map((href) => hrefToNavItem.get(href))
                .filter((item): item is NavigationLeafItem => item !== undefined)
              if (!items.length) return null
              return (
                <CommandGroup key={group.label} heading={group.label}>
                  {items.map((item) => {
                    const Icon = item.icon
                    return (
                      <CommandItem
                        key={item.href}
                        value={item.label.toLowerCase()}
                        onSelect={() => {
                          router.push(item.href)
                          handleClose()
                        }}
                      >
                        <Icon className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
                        {item.label}
                      </CommandItem>
                    )
                  })}
                </CommandGroup>
              )
            })}

            <CommandSeparator />

            <CommandGroup heading="Quick Actions">
              {QUICK_ACTIONS.map((action) => (
                <CommandItem
                  key={action.href}
                  value={action.label.toLowerCase()}
                  onSelect={() => {
                    router.push(action.href)
                    handleClose()
                  }}
                >
                  {action.label}
                </CommandItem>
              ))}
            </CommandGroup>

            <CommandSeparator />

            <CommandGroup heading="AI">
              <CommandItem
                value="ask finqor ai"
                onSelect={() => setShowAIPanel(true)}
              >
                <Sparkles className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
                Ask Finqor AI anything…
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </>
      ) : (
        <div className="flex flex-col">
          {/* Back button */}
          <div className="flex items-center border-b border-border px-3 py-2">
            <button
              type="button"
              onClick={() => setShowAIPanel(false)}
              className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to search
            </button>
          </div>

          {/* AI response area */}
          <div className="p-4">
            <div className="rounded-md border border-border/60 bg-background p-3">
              <p className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                Finqor AI
              </p>
              <div className="min-h-[220px] whitespace-pre-wrap text-sm text-foreground">
                {aiResponse || "Ask anything about your financials..."}
                {isStreaming ? <span className="animate-pulse">▊</span> : null}
              </div>
              {streamError ? (
                <p className="mt-2 text-xs text-red-400">{streamError}</p>
              ) : null}
              {traceId ? (
                <p className="mt-2 text-[10px] text-muted-foreground">Trace: {traceId}</p>
              ) : null}
            </div>

            {/* AI input */}
            <div className="mt-3 flex items-center gap-2">
              <Input
                placeholder="Ask anything about your financials..."
                value={aiPrompt}
                onChange={(event) => setAiPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    void handleAISubmit()
                  }
                }}
                autoFocus
              />
              <button
                type="button"
                onClick={() => void handleAISubmit()}
                className="shrink-0 rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
                disabled={isStreaming}
              >
                {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </CommandDialog>
  )
}
