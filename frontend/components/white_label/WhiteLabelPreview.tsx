"use client"

interface WhiteLabelPreviewProps {
  brandName: string
  logoUrl: string
  primaryColour: string
  secondaryColour: string
}

export function WhiteLabelPreview({
  brandName,
  logoUrl,
  primaryColour,
  secondaryColour,
}: WhiteLabelPreviewProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ backgroundColor: primaryColour }}
      >
        <div className="flex items-center gap-2">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt={brandName} className="h-6 w-6 rounded object-cover" />
          ) : (
            <div className="h-6 w-6 rounded bg-white/20" />
          )}
          <span className="text-sm font-semibold text-white">{brandName || "Your Brand"}</span>
        </div>
        <span className="text-xs text-white/80">Preview</span>
      </div>
      <div className="grid grid-cols-[180px_1fr] bg-background">
        <aside
          className="min-h-[180px] border-r border-border p-3 text-xs"
          style={{ backgroundColor: secondaryColour }}
        >
          <p className="font-medium text-foreground">Menu</p>
          <p className="mt-2 text-muted-foreground">Dashboard</p>
          <p className="text-muted-foreground">Reports</p>
          <p className="text-muted-foreground">Settings</p>
        </aside>
        <div className="p-4">
          <h4 className="text-sm font-semibold text-foreground">Branded Workspace</h4>
          <p className="mt-2 text-xs text-muted-foreground">
            This preview shows your logo, brand text, and primary colours.
          </p>
        </div>
      </div>
    </div>
  )
}

