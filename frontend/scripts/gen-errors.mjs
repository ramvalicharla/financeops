import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

const modules = [
  { path: '(dashboard)/[orgSlug]/[entitySlug]/accounting', name: 'Accounting' },
  { path: '(dashboard)/reconciliation', name: 'Reconciliation' },
  { path: '(dashboard)/treasury', name: 'Treasury' },
  { path: '(dashboard)/reports', name: 'Reports' },
  { path: '(dashboard)/advisory', name: 'Advisory' },
  { path: '(dashboard)/close', name: 'Month-End Close' },
  { path: '(dashboard)/consolidation', name: 'Consolidation' },
  { path: '(dashboard)/audit', name: 'Audit' },
  { path: '(dashboard)/board-pack', name: 'Board Pack' },
  { path: '(dashboard)/forecast', name: 'Forecast' },
  { path: '(dashboard)/scenarios', name: 'Scenarios' },
  { path: '(dashboard)/tax', name: 'Tax' },
  { path: '(dashboard)/transfer-pricing', name: 'Transfer Pricing' },
  { path: '(dashboard)/statutory', name: 'Statutory' },
  { path: '(dashboard)/fixed-assets', name: 'Fixed Assets' },
  { path: '(dashboard)/expenses', name: 'Expenses' },
]

const errorTemplate = (moduleName) => `"use client"

import { useEffect } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ErrorBoundaryProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function ${moduleName.replace(/[^a-zA-Z]/g, '')}ErrorBoundary({ error, reset }: ErrorBoundaryProps) {
  useEffect(() => {
    // Log to error reporting (Sentry is already configured in the API client)
    console.error("[${moduleName}] Runtime error:", error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-5 p-8">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10">
        <AlertTriangle className="h-6 w-6 text-destructive" />
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-lg font-semibold text-foreground">${moduleName} encountered an error</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          Something went wrong loading this module. Your data is safe — this is an isolated view error.
        </p>
        {error.digest ? (
          <p className="font-mono text-xs text-muted-foreground">Error ID: {error.digest}</p>
        ) : null}
      </div>
      <Button onClick={reset} variant="outline" size="sm">
        <RefreshCw className="mr-2 h-3 w-3" /> Try again
      </Button>
    </div>
  )
}
`

let created = 0
for (const mod of modules) {
  const dir = path.join(root, 'app', mod.path)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
  const errorFile = path.join(dir, 'error.tsx')
  if (!fs.existsSync(errorFile)) {
    fs.writeFileSync(errorFile, errorTemplate(mod.name), 'utf8')
    console.log('  CREATED', path.relative(root, errorFile))
    created++
  } else {
    console.log('  EXISTS', path.relative(root, errorFile))
  }
}

console.log(`\nDone: Created ${created} error boundaries`)
