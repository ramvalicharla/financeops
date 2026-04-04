"use client"

import { useEffect, useMemo, useState } from "react"
import { FormField } from "@/components/ui/FormField"
import type { WhiteLabelConfig } from "@/lib/types/white-label"
import { getWhiteLabelConfig, updateWhiteLabelConfig } from "@/lib/api/white-label"
import { WhiteLabelPreview } from "@/components/white_label/WhiteLabelPreview"

interface BrandingState {
  brand_name: string
  logo_url: string
  favicon_url: string
  primary_colour: string
  secondary_colour: string
  font_family: string
  hide_powered_by: boolean
  support_email: string
  support_url: string
  custom_css: string
}

interface BrandingEditorProps {
  initialConfig?: WhiteLabelConfig
  readOnly?: boolean
}

const emptyState: BrandingState = {
  brand_name: "",
  logo_url: "",
  favicon_url: "",
  primary_colour: "#1f2937",
  secondary_colour: "#111827",
  font_family: "inter",
  hide_powered_by: false,
  support_email: "",
  support_url: "",
  custom_css: "",
}

export function BrandingEditor({ initialConfig, readOnly = false }: BrandingEditorProps) {
  const [config, setConfig] = useState<WhiteLabelConfig | null>(initialConfig ?? null)
  const [state, setState] = useState<BrandingState>(emptyState)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const payload = initialConfig ?? (await getWhiteLabelConfig())
        setConfig(payload)
        setState({
          brand_name: payload.brand_name ?? "",
          logo_url: payload.logo_url ?? "",
          favicon_url: payload.favicon_url ?? "",
          primary_colour: payload.primary_colour ?? "#1f2937",
          secondary_colour: payload.secondary_colour ?? "#111827",
          font_family: payload.font_family ?? "inter",
          hide_powered_by: payload.hide_powered_by,
          support_email: payload.support_email ?? "",
          support_url: payload.support_url ?? "",
          custom_css: payload.custom_css ?? "",
        })
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load branding config")
      }
    }

    if (!config) {
      void load()
    }
  }, [config, initialConfig])

  const updateField = <K extends keyof BrandingState>(key: K, value: BrandingState[K]) => {
    setState((previous) => ({ ...previous, [key]: value }))
  }

  const save = async () => {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const payload = await updateWhiteLabelConfig({
        brand_name: state.brand_name || null || undefined,
        logo_url: state.logo_url || null || undefined,
        favicon_url: state.favicon_url || null || undefined,
        primary_colour: state.primary_colour || null || undefined,
        secondary_colour: state.secondary_colour || null || undefined,
        font_family: state.font_family || null || undefined,
        hide_powered_by: state.hide_powered_by,
        support_email: state.support_email || null || undefined,
        support_url: state.support_url || null || undefined,
        custom_css: state.custom_css || null || undefined,
      })
      setConfig(payload)
      setMessage("Branding updated.")
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update branding")
    } finally {
      setSaving(false)
    }
  }

  const preview = useMemo(
    () => ({
      brandName: state.brand_name || "Your Brand",
      logoUrl: state.logo_url,
      primaryColour: state.primary_colour || "#1f2937",
      secondaryColour: state.secondary_colour || "#111827",
    }),
    [state.brand_name, state.logo_url, state.primary_colour, state.secondary_colour],
  )

  return (
    <div className="space-y-4">
      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-2">
        <FormField id="brand-name" label="Brand name">
          <input
            value={state.brand_name}
            onChange={(event) => updateField("brand_name", event.target.value)}
            disabled={readOnly}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <FormField id="brand-logo-url" label="Logo URL">
          <input
            value={state.logo_url}
            onChange={(event) => updateField("logo_url", event.target.value)}
            disabled={readOnly}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <FormField id="brand-favicon-url" label="Favicon URL">
          <input
            value={state.favicon_url}
            onChange={(event) => updateField("favicon_url", event.target.value)}
            disabled={readOnly}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <label className="text-xs text-muted-foreground">
          Primary Colour
          <input
            aria-label="Primary colour"
            value={state.primary_colour}
            onChange={(event) => updateField("primary_colour", event.target.value)}
            disabled={readOnly}
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="#112233"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Secondary Colour
          <input
            aria-label="Secondary colour"
            value={state.secondary_colour}
            onChange={(event) => updateField("secondary_colour", event.target.value)}
            disabled={readOnly}
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="#1f2937"
          />
        </label>
        <FormField id="brand-font-family" label="Font family">
          <select
            value={state.font_family}
            onChange={(event) => updateField("font_family", event.target.value)}
            disabled={readOnly}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="inter">Inter</option>
            <option value="plus_jakarta">Plus Jakarta</option>
            <option value="geist">Geist</option>
            <option value="dm_sans">DM Sans</option>
          </select>
        </FormField>
        <FormField id="brand-support-email" label="Support email">
          <input
            value={state.support_email}
            onChange={(event) => updateField("support_email", event.target.value)}
            disabled={readOnly}
            autoComplete="email"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <FormField
          id="brand-support-url"
          label="Support URL"
          hint="Enter your custom domain e.g. app.yourcompany.com"
        >
          <input
            value={state.support_url}
            onChange={(event) => updateField("support_url", event.target.value)}
            disabled={readOnly}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
        <div className="md:col-span-2">
          <FormField id="brand-custom-css" label="Custom CSS" hint="Max 10,000 characters">
            <textarea
              value={state.custom_css}
              onChange={(event) => updateField("custom_css", event.target.value)}
              disabled={readOnly}
              rows={6}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-xs text-foreground"
            />
          </FormField>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            id="brand-hide-powered-by"
            type="checkbox"
            checked={state.hide_powered_by}
            onChange={(event) => updateField("hide_powered_by", event.target.checked)}
            disabled={readOnly}
          />
          <label htmlFor="brand-hide-powered-by">Hide Powered by FinanceOps footer</label>
        </div>
      </section>

      <WhiteLabelPreview
        brandName={preview.brandName}
        logoUrl={preview.logoUrl}
        primaryColour={preview.primaryColour}
        secondaryColour={preview.secondaryColour}
      />

      {readOnly ? (
        <p className="text-xs text-muted-foreground">Read-only view for platform admin.</p>
      ) : (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save Branding"}
          </button>
          {message ? <span className="text-xs text-muted-foreground">{message}</span> : null}
          {error ? <span className="text-xs text-[hsl(var(--brand-danger))]">{error}</span> : null}
        </div>
      )}
    </div>
  )
}
