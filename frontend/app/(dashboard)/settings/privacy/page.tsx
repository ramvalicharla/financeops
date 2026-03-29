import Link from "next/link"

export default function PrivacySettingsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Privacy Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your consent preferences and GDPR data rights.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <Link href="/settings/privacy/consent" className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-lg font-medium text-foreground">My Consent Preferences</h2>
          <p className="mt-2 text-sm text-muted-foreground">Manage analytics, marketing, AI processing, and sharing preferences.</p>
        </Link>

        <Link href="/settings/privacy/my-data" className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-lg font-medium text-foreground">My Data Export</h2>
          <p className="mt-2 text-sm text-muted-foreground">Request and download your personal data export.</p>
        </Link>

        <article className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-lg font-medium text-foreground">Delete My Account</h2>
          <p className="mt-2 text-sm text-muted-foreground">Submit a GDPR erasure request after confirmation.</p>
          <button type="button" className="mt-3 rounded-md border border-[hsl(var(--brand-danger)/0.5)] px-3 py-2 text-sm text-[hsl(var(--brand-danger))]">
            Request Erasure
          </button>
        </article>
      </section>
    </div>
  )
}

