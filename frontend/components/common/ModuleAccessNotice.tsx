"use client"

export function ModuleAccessNotice({
  message,
  title = "Access limited",
}: {
  message: string
  title?: string
}) {
  return (
    <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-200">
        {title}
      </h2>
      <p className="mt-2 text-sm text-amber-100">{message}</p>
    </section>
  )
}
