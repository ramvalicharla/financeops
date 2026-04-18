import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const base = path.join(root, 'app')

// Pages that need a coming-soon stub (no backend data shape identified)
const stubs = [
  // Accounting
  { dir: '(dashboard)/[orgSlug]/[entitySlug]/accounting/revaluation', title: 'FX Revaluation', desc: 'Foreign currency revaluation adjustments for period-end close.' },
  { dir: '(dashboard)/[orgSlug]/[entitySlug]/accounting/trial-balance', title: 'Entity Trial Balance', desc: 'View the trial balance for this entity and period.' },
  { dir: '(dashboard)/[orgSlug]/[entitySlug]/accounting/journals', title: 'Journal Entries', desc: 'Create, review and approve journal entries for this entity.' },

  // Advisory detail pages
  { dir: '(dashboard)/advisory/fdd/[id]', title: 'FDD Report', desc: 'Financial due diligence report details and findings.', paramKey: 'id' },
  { dir: '(dashboard)/advisory/fdd/[id]/report', title: 'FDD Generated Report', desc: 'View the generated FDD report document.', paramKey: 'id' },
  { dir: '(dashboard)/advisory/ma/[id]', title: 'M&A Deal', desc: 'Merger and acquisition deal overview and timeline.', paramKey: 'id' },
  { dir: '(dashboard)/advisory/ma/[id]/documents', title: 'Deal Documents', desc: 'Due diligence documents for this M&A transaction.', paramKey: 'id' },
  { dir: '(dashboard)/advisory/ma/[id]/valuation', title: 'Deal Valuation', desc: 'Valuation models and assumptions for this transaction.', paramKey: 'id' },
  { dir: '(dashboard)/advisory/ppa/[id]', title: 'PPA Engagement', desc: 'Purchase price allocation engagement details.', paramKey: 'id' },

  // Budget
  { dir: '(dashboard)/budget/[year]', title: 'Budget', desc: 'Annual budget overview and variance tracking.', paramKey: 'year' },
  { dir: '(dashboard)/budget/[year]/edit', title: 'Edit Budget', desc: 'Edit budget line items for this fiscal year.', paramKey: 'year' },

  // Consolidation
  { dir: '(dashboard)/consolidation/runs/[id]', title: 'Consolidation Run', desc: 'Multi-entity consolidation run details and adjustments.', paramKey: 'id' },

  // Detail pages
  { dir: '(dashboard)/expenses/[id]', title: 'Expense Detail', desc: 'Expense claim details, approvals and receipts.', paramKey: 'id' },
  { dir: '(dashboard)/fixed-assets/[id]', title: 'Asset Detail', desc: 'Fixed asset register entry with depreciation schedule.', paramKey: 'id' },
  { dir: '(dashboard)/forecast/[id]', title: 'Forecast Detail', desc: 'Forecast run details, assumptions and projections.', paramKey: 'id' },
  { dir: '(dashboard)/marketplace/[id]', title: 'Template Detail', desc: 'Template preview, ratings and installation options.', paramKey: 'id' },
  { dir: '(dashboard)/prepaid/[id]', title: 'Prepaid Schedule', desc: 'Prepaid expense amortisation schedule and entries.', paramKey: 'id' },
  { dir: '(dashboard)/reports/[id]', title: 'Report Detail', desc: 'Report output viewer with export and share options.', paramKey: 'id' },
  { dir: '(dashboard)/tax/[id]', title: 'Tax Position Detail', desc: 'Tax position detail, provisions and supporting notes.', paramKey: 'id' },
  { dir: '(dashboard)/transfer-pricing/[id]', title: 'TP Document', desc: 'Transfer pricing documentation and benchmarking data.', paramKey: 'id' },
  { dir: '(dashboard)/anomalies/[id]', title: 'Anomaly Detail', desc: 'Anomaly investigation details, root cause and resolution.', paramKey: 'id' },
  { dir: '(dashboard)/audit/[engagement_id]', title: 'Audit Engagement', desc: 'Audit engagement details, PBC tracker and evidence.', paramKey: 'engagement_id' },
  { dir: '(dashboard)/board-pack/[id]', title: 'Board Pack', desc: 'Board pack document with narrative and financial statements.', paramKey: 'id' },

  // Settings
  { dir: '(dashboard)/settings/airlock/[id]', title: 'Airlock Item', desc: 'Airlock review item details and approval workflow.', paramKey: 'id' },

  // Admin
  { dir: '(admin)/admin/white-label/[tenant_id]', title: 'White Label Config', desc: 'White label configuration for this tenant.', paramKey: 'tenant_id' },

  // Control plane
  { dir: 'control-plane/airlock/[itemId]', title: 'Airlock Item', desc: 'Platform airlock entry review and disposition.', paramKey: 'itemId', isControlPlane: true },
  { dir: 'control-plane/entities/[entityId]', title: 'Entity Detail', desc: 'Platform entity details and configuration.', paramKey: 'entityId', isControlPlane: true },
  { dir: 'control-plane/intents/[intentId]', title: 'Intent Detail', desc: 'Platform intent record and execution history.', paramKey: 'intentId', isControlPlane: true },
  { dir: 'control-plane/jobs/[jobId]', title: 'Job Detail', desc: 'Background job execution log and status.', paramKey: 'jobId', isControlPlane: true },
  { dir: 'control-plane/snapshots/[snapshotId]', title: 'Snapshot Detail', desc: 'Platform snapshot details and restore options.', paramKey: 'snapshotId', isControlPlane: true },

  // Scenarios
  { dir: '(dashboard)/scenarios/[id]', title: 'Scenario Detail', desc: 'Scenario analysis detail view.', paramKey: 'id' },
]

const pageClientTemplate = (title, desc, paramKey) => `"use client"

import { useParams } from "next/navigation"
import { ArrowLeft, Construction } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function ${title.replace(/[^a-zA-Z]/g, '')}Page() {
  const params = useParams()
  const id = params?.${paramKey ?? 'id'} ?? null

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 p-6">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-card">
        <Construction className="h-7 w-7 text-muted-foreground" />
      </div>
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">${title}</h1>
        <p className="text-sm text-muted-foreground max-w-md">${desc}</p>
        {id ? (
          <p className="font-mono text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
            ID: {Array.isArray(id) ? id[0] : id}
          </p>
        ) : null}
      </div>
      <p className="rounded-full border border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
        Full implementation in progress — wires to live API
      </p>
      <Button variant="outline" size="sm" asChild>
        <Link href=".."><ArrowLeft className="mr-2 h-3 w-3" /> Back</Link>
      </Button>
    </div>
  )
}
`

const pageTemplate = (title) => `import PageClient from "./PageClient"
import { createMetadata } from "@/lib/metadata"
export const metadata = createMetadata("${title}")
export default function Page() { return <PageClient /> }
`

let created = 0
for (const stub of stubs) {
  const dir = path.join(base, stub.dir)
  fs.mkdirSync(dir, { recursive: true })

  const clientFile = path.join(dir, 'PageClient.tsx')
  const pageFile = path.join(dir, 'page.tsx')

  const shouldWrite = (f) => {
    if (!fs.existsSync(f)) return true
    const content = fs.readFileSync(f, 'utf8').trim()
    return content.length === 0
  }

  if (shouldWrite(clientFile)) {
    fs.writeFileSync(clientFile, pageClientTemplate(stub.title, stub.desc, stub.paramKey), 'utf8')
    created++
    console.log('  WROTE', path.relative(root, clientFile))
  } else {
    console.log('  SKIP (has content)', path.relative(root, clientFile))
  }

  if (shouldWrite(pageFile)) {
    fs.writeFileSync(pageFile, pageTemplate(stub.title), 'utf8')
    created++
  }
}

console.log(`\nDone: Created/filled ${created} stub files`)
