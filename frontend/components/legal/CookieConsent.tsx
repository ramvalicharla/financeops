"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

export function CookieConsent() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const accepted = window.localStorage.getItem("cookie_consent")
    if (!accepted) {
      setShow(true)
    }
  }, [])

  const accept = () => {
    window.localStorage.setItem("cookie_consent", "essential_only")
    setShow(false)
  }

  if (!show) {
    return null
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-700 bg-gray-900 p-4 md:left-60">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-6">
        <p className="text-sm text-gray-300">
          We use essential cookies only for authentication and security. No tracking or advertising cookies.{" "}
          <Link href="/legal/cookies" className="text-blue-400 hover:underline">
            Learn more
          </Link>
        </p>
        <button
          onClick={accept}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
          type="button"
        >
          Accept Cookies
        </button>
      </div>
    </div>
  )
}
