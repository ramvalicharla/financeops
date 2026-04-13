"use client"

import { useEffect, useState } from "react"

const VALUE_PROPS = [
  "IFRS 15/16 computed automatically",
  "23 ERP connectors including Tally, Zoho & SAP",
  "Bank reconciliation in seconds",
  "Board pack generated, not assembled",
] as const

export function ValueProps() {
  const [index, setIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const id = setInterval(() => {
      setVisible(false)
      const swapId = setTimeout(() => {
        setIndex((i) => (i + 1) % VALUE_PROPS.length)
        setVisible(true)
      }, 300)
      return () => clearTimeout(swapId)
    }, 3000)
    return () => clearInterval(id)
  }, [])

  return (
    <p
      className="text-sm text-muted-foreground transition-opacity duration-300 min-h-[1.25rem]"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {VALUE_PROPS[index]}
    </p>
  )
}
