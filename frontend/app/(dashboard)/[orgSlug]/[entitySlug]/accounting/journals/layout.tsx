import type { ReactNode } from "react"

interface JournalsLayoutProps {
  children: ReactNode
  modal: ReactNode
}

export default function JournalsLayout({ children, modal }: JournalsLayoutProps) {
  return (
    <>
      {children}
      {modal}
    </>
  )
}
