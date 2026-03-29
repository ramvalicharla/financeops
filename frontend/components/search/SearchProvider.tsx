"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { CommandPalette } from "@/components/search/CommandPalette"

type SearchContextValue = {
  isOpen: boolean
  openPalette: () => void
  closePalette: () => void
}

const SearchContext = createContext<SearchContextValue | null>(null)

export function SearchProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)

  const openPalette = useCallback(() => {
    setIsOpen(true)
  }, [])

  const closePalette = useCallback(() => {
    setIsOpen(false)
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k"
      if (isShortcut) {
        event.preventDefault()
        setIsOpen(true)
      } else if (event.key === "Escape") {
        setIsOpen(false)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const value = useMemo(
    () => ({
      isOpen,
      openPalette,
      closePalette,
    }),
    [closePalette, isOpen, openPalette],
  )

  return (
    <SearchContext.Provider value={value}>
      {children}
      <CommandPalette isOpen={isOpen} onClose={closePalette} />
    </SearchContext.Provider>
  )
}

export const useSearch = (): SearchContextValue => {
  const context = useContext(SearchContext)
  if (!context) {
    throw new Error("useSearch must be used within SearchProvider")
  }
  return context
}

