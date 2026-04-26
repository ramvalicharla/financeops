"use client"

import { X } from "lucide-react"
import { type ReactNode, useEffect, useId, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

const TRANSITION_MS = 200

const sizeClassMap = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
} as const

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",")

const getFocusableElements = (container: HTMLElement | null): HTMLElement[] => {
  if (!container) {
    return []
  }

  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) =>
      !element.hasAttribute("disabled") &&
      element.getAttribute("aria-hidden") !== "true",
  )
}

/**
 * Props for the shared modal dialog primitive.
 */
export interface DialogProps {
  /** Controls whether the dialog is visible. */
  open: boolean
  /** Called when the dialog should close. */
  onClose: () => void
  /** Accessible title rendered in the dialog header. */
  title: string
  /** Optional supporting copy announced by assistive technology. */
  description?: string
  /** Main dialog content. */
  children: ReactNode
  /** Width preset for the dialog panel. */
  size?: keyof typeof sizeClassMap
  /** Optional className appended to the panel — use for one-off width overrides (e.g. max-w-[640px]). */
  className?: string
}

/**
 * Accessible modal dialog with focus management, backdrop dismissal, and Escape handling.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
  className,
}: DialogProps) {
  const [mounted, setMounted] = useState(open)
  const [visible, setVisible] = useState(open)
  const panelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const restoreFocusRef = useRef<HTMLElement | null>(null)
  const previousOpenRef = useRef(open)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    if (open) {
      restoreFocusRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
      setMounted(true)
      const frame = window.requestAnimationFrame(() => setVisible(true))
      return () => window.cancelAnimationFrame(frame)
    }

    setVisible(false)
    const timeout = window.setTimeout(() => setMounted(false), TRANSITION_MS)
    return () => window.clearTimeout(timeout)
  }, [open])

  useEffect(() => {
    if (!mounted) {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [mounted])

  useEffect(() => {
    if (!open) {
      return
    }

    const timeout = window.setTimeout(() => {
      const focusable = getFocusableElements(panelRef.current)
      ;(focusable[0] ?? closeButtonRef.current ?? panelRef.current)?.focus()
    }, 0)
    return () => window.clearTimeout(timeout)
  }, [open])

  useEffect(() => {
    if (previousOpenRef.current && !open) {
      restoreFocusRef.current?.focus()
    }
    previousOpenRef.current = open
  }, [open])

  useEffect(() => {
    if (!open) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        onClose()
        return
      }

      if (event.key !== "Tab") {
        return
      }

      const focusable = getFocusableElements(panelRef.current)
      if (!focusable.length) {
        event.preventDefault()
        panelRef.current?.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (event.shiftKey) {
        if (active === first || !panelRef.current?.contains(active)) {
          event.preventDefault()
          last?.focus()
        }
        return
      }

      if (active === last) {
        event.preventDefault()
        first?.focus()
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onClose, open])

  if (!mounted || typeof document === "undefined") {
    return null
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className={cn(
          "absolute inset-0 bg-black/60 transition-opacity duration-200",
          visible ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={cn(
          "relative z-10 flex max-h-[90vh] w-full flex-col overflow-hidden rounded-lg border border-border bg-card shadow-2xl outline-none transition-all duration-200",
          sizeClassMap[size],
          visible ? "translate-y-0 scale-100 opacity-100" : "translate-y-4 scale-95 opacity-0",
          className,
        )}
        role="dialog"
        tabIndex={-1}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold text-foreground">
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          <button
            ref={closeButtonRef}
            aria-label="Close dialog"
            className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            onClick={onClose}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 overflow-auto p-5">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
