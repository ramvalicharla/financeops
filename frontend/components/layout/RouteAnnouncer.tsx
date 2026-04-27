"use client"

import { useEffect, useRef } from "react"
import { usePathname } from "next/navigation"

export function RouteAnnouncer() {
  const pathname = usePathname()
  const announcerRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    // Move focus to the main landmark so keyboard users start at page content
    const main = document.getElementById("main-content")
    if (main) {
      main.setAttribute("tabindex", "-1")
      main.focus({ preventScroll: true })
    }

    // Wait one paint for the new page's h1 to render before reading it
    const id = setTimeout(() => {
      const heading = document.querySelector("h1")?.textContent?.trim()
      if (announcerRef.current) {
        announcerRef.current.textContent = heading ?? document.title
      }
    }, 100)

    return () => clearTimeout(id)
  }, [pathname])

  return (
    <p
      ref={announcerRef}
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    />
  )
}
