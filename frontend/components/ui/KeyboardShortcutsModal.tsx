"use client"

import { useEffect, useState } from "react"
import { Search, Command, MoveUp, Plus, Settings } from "lucide-react"

interface Shortcut {
  keys: string[]
  description: string
  icon: React.ElementType
}

const SHORTCUTS: Shortcut[] = [
  { keys: ["Ctrl", "K"], description: "Open Command Palette / Global Search", icon: Search },
  { keys: ["Ctrl", "N"], description: "New Entry (Journals / Expenses)", icon: Plus },
  { keys: ["Ctrl", "/"], description: "Search current view", icon: Search },
  { keys: ["?"], description: "Show this legendary shortcuts modal", icon: Command },
]

export function KeyboardShortcutsModal() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return
      }

      if (e.key === "?" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        setOpen((prev) => !prev)
      } else if (e.key === "Escape") {
        setOpen(false)
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div 
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="shortcuts-title" className="text-lg font-semibold text-foreground">
            Keyboard Shortcuts
          </h2>
          <button 
            onClick={() => setOpen(false)}
            className="text-muted-foreground hover:text-foreground p-1 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close modal"
          >
            Esc
          </button>
        </div>

        <div className="space-y-4">
          {SHORTCUTS.map((shortcut, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                  <shortcut.icon className="h-4 w-4" />
                </div>
                <span className="text-sm font-medium text-foreground">{shortcut.description}</span>
              </div>
              <div className="flex gap-1">
                {shortcut.keys.map((key, j) => (
                  <kbd 
                    key={j}
                    className="inline-flex h-6 min-w-6 items-center justify-center rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground"
                  >
                    {key}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
