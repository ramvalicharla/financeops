"use client"

import type { MutableRefObject } from "react"
import { useTheme } from "next-themes"
import { signOut } from "next-auth/react"
import { Button } from "@/components/ui/button"

export interface TopbarProfileMenuProps {
  menuId: string
  menuRef: MutableRefObject<HTMLDivElement | null>
  open: boolean
  onClose: () => void
  triggerRef: MutableRefObject<HTMLButtonElement | null>
  userEmail: string
  userName: string
  onToggle: () => void
}

export function TopbarProfileMenu({
  menuId,
  menuRef,
  open,
  onClose,
  triggerRef,
  userEmail,
  userName,
  onToggle,
}: TopbarProfileMenuProps) {
  const { theme, setTheme } = useTheme()

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-medium text-accent-foreground"
        onClick={onToggle}
        type="button"
      >
        {userName.slice(0, 1).toUpperCase()}
      </button>
      {open ? (
        <div
          id={menuId}
          ref={menuRef}
          role="menu"
          tabIndex={-1}
          className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-card p-3 shadow-lg"
          onKeyDown={(event) => {
            if (event.key === "Tab") {
              onClose()
              return
            }
            if (event.key === "Escape") {
              onClose()
              triggerRef.current?.focus()
              return
            }
            const items = menuRef.current?.querySelectorAll('[role="menuitem"]')
            if (!items?.length) {
              return
            }
            const current = document.activeElement
            const currentIndex = Array.from(items).indexOf(current as Element)
            if (event.key === "ArrowDown") {
              event.preventDefault()
              const next = items[currentIndex + 1] ?? items[0]
              ;(next as HTMLElement)?.focus()
            }
            if (event.key === "ArrowUp") {
              event.preventDefault()
              const previous = items[currentIndex - 1] ?? items[items.length - 1]
              ;(previous as HTMLElement)?.focus()
            }
          }}
        >
          <p className="text-sm font-medium text-foreground">{userName}</p>
          <p className="text-xs text-muted-foreground">{userEmail}</p>
          <div className="mt-4 border-t border-border pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Theme
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={theme === "light" ? "default" : "outline"}
                className="flex-1 text-xs"
                onClick={() => setTheme("light")}
              >
                Light
              </Button>
              <Button
                size="sm"
                variant={theme === "dark" ? "default" : "outline"}
                className="flex-1 text-xs"
                onClick={() => setTheme("dark")}
              >
                Dark
              </Button>
              <Button
                size="sm"
                variant={theme === "system" ? "default" : "outline"}
                className="flex-1 text-xs"
                onClick={() => setTheme("system")}
              >
                System
              </Button>
            </div>
          </div>
          <Button
            className="mt-3 w-full"
            size="sm"
            variant="outline"
            onClick={() => signOut({ callbackUrl: "/login" })}
            type="button"
            role="menuitem"
          >
            Sign out
          </Button>
        </div>
      ) : null}
    </div>
  )
}
