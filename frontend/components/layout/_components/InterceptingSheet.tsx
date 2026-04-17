"use client"

import { useRouter } from "next/navigation"
import { Sheet } from "@/components/ui/Sheet"

interface InterceptingSheetProps {
  title: string
  description?: string
  children: React.ReactNode
  width?: string
}

export function InterceptingSheet({ title, description, children, width }: InterceptingSheetProps) {
  const router = useRouter()

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      router.back()
    }
  }

  // We enforce open=true because the act of rendering this route means it should be visible
  return (
    <Sheet 
      open={true} 
      onClose={() => handleOpenChange(false)} 
      title={title} 
      description={description} 
      width={width || "max-w-3xl"}
    >
      {children}
    </Sheet>
  )
}
