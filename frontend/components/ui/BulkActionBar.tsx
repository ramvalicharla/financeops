"use client"

import { ReactNode } from "react"
import { motion, AnimatePresence } from "framer-motion"

export interface BulkActionBarProps {
  selectedCount: number
  onClearSelection: () => void
  actions: ReactNode
}

export function BulkActionBar({
  selectedCount,
  onClearSelection,
  actions,
}: BulkActionBarProps) {
  return (
    <AnimatePresence>
      {selectedCount > 0 && (
        <motion.div
          initial={{ y: 50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 50, opacity: 0 }}
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transition-shadow hover:shadow-lg"
        >
          <div className="flex items-center gap-4 rounded-full border border-border bg-card px-6 py-3 shadow-md">
            <div className="flex items-center gap-2 border-r border-border pr-4">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                {selectedCount}
              </span>
              <span className="text-sm font-medium text-foreground">
                Items selected
              </span>
            </div>
            <div className="flex items-center gap-2">
              {actions}
              <button
                type="button"
                onClick={onClearSelection}
                className="ml-2 text-sm text-muted-foreground hover:text-foreground underline underline-offset-2"
              >
                Clear
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
