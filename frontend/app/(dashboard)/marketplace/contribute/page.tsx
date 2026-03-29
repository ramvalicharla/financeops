"use client"

import { useEffect, useState } from "react"
import {
  getMarketplaceContributorDashboard,
  registerMarketplaceContributor,
  submitMarketplaceTemplate,
} from "@/lib/api/marketplace"
import type { MarketplaceContributor } from "@/lib/types/marketplace"

const templateTypeOptions = [
  "mis_template",
  "report_template",
  "board_pack",
  "classification_mapping",
  "consolidation_template",
  "paysheet_template",
  "industry_pack",
  "fdd_template",
  "budget_template",
  "forecast_template",
] as const

export default function MarketplaceContributePage() {
  const [contributor, setContributor] = useState<MarketplaceContributor | null>(null)
  const [displayName, setDisplayName] = useState("")
  const [bio, setBio] = useState("")

  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [templateType, setTemplateType] = useState<string>("mis_template")
  const [industry, setIndustry] = useState("")
  const [priceCredits, setPriceCredits] = useState(0)
  const [tagsInput, setTagsInput] = useState("")
  const [templateDataText, setTemplateDataText] = useState("{\n  \"line_items\": []\n}")

  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadContributor = async () => {
    try {
      const payload = await getMarketplaceContributorDashboard()
      setContributor(payload.contributor)
      if (!displayName) {
        setDisplayName(payload.contributor.display_name)
      }
      if (!bio && payload.contributor.bio) {
        setBio(payload.contributor.bio)
      }
    } catch {
      setContributor(null)
    }
  }

  useEffect(() => {
    void loadContributor()
  }, [])

  const onRegister = async () => {
    setError(null)
    setMessage(null)
    try {
      const row = await registerMarketplaceContributor({
        display_name: displayName,
        bio: bio || undefined,
      })
      setContributor(row)
      setMessage("Contributor profile created.")
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : "Failed to register contributor")
    }
  }

  const onSubmitTemplate = async () => {
    setError(null)
    setMessage(null)
    try {
      const parsed = JSON.parse(templateDataText) as Record<string, unknown>
      await submitMarketplaceTemplate({
        title,
        description,
        template_type: templateType,
        price_credits: priceCredits,
        template_data: parsed,
        industry: industry || undefined,
        tags: tagsInput
          .split(",")
          .map((tag) => tag.trim())
          .filter((tag) => tag.length > 0),
      })
      setMessage("Template submitted for review.")
      setTitle("")
      setDescription("")
      setTagsInput("")
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit template")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Contributor Portal</h1>
        <p className="text-sm text-muted-foreground">
          Register your profile and submit templates to the marketplace review queue.
        </p>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Step 1: Register as Contributor</h2>
        {contributor ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Registered as <span className="text-foreground">{contributor.display_name}</span> (
            {contributor.contributor_tier})
          </p>
        ) : (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              placeholder="Display name"
            />
            <input
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              placeholder="Short bio"
            />
            <button
              type="button"
              onClick={() => void onRegister()}
              className="w-fit rounded-md border border-border px-3 py-2 text-sm text-foreground"
            >
              Register Contributor
            </button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Step 2: Submit Template</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Template title"
          />
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Short description"
          />
          <select
            value={templateType}
            onChange={(event) => setTemplateType(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            {templateTypeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <input
            value={industry}
            onChange={(event) => setIndustry(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Industry (optional)"
          />
          <input
            type="number"
            value={priceCredits}
            min={0}
            onChange={(event) => setPriceCredits(Number(event.target.value))}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Price in credits"
          />
          <input
            value={tagsInput}
            onChange={(event) => setTagsInput(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Tags (comma separated)"
          />
          <label className="md:col-span-2 text-xs text-muted-foreground">
            Template Data JSON
            <textarea
              value={templateDataText}
              onChange={(event) => setTemplateDataText(event.target.value)}
              rows={10}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
            />
          </label>
          <button
            type="button"
            onClick={() => void onSubmitTemplate()}
            disabled={!contributor}
            className="w-fit rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
          >
            Submit for Review
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Step 3: Confirmation</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Submitted templates are reviewed by platform admins before publication.
        </p>
      </section>

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
    </div>
  )
}
