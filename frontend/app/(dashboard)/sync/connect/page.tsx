import { ConnectSourceForm } from "@/components/sync/ConnectSourceForm"

export default function ConnectSourcePage() {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Connect Source</h2>
        <p className="text-sm text-muted-foreground">
          Configure, test, and start your first sync run.
        </p>
      </div>
      <ConnectSourceForm />
    </section>
  )
}
