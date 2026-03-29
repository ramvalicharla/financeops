"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export type EvidenceUploaderProps = {
  requestId: string
  existingUrls: string[]
  onSave: (urls: string[]) => Promise<void>
}

export function EvidenceUploader({ requestId, existingUrls, onSave }: EvidenceUploaderProps) {
  const [files, setFiles] = useState<string[]>(existingUrls)
  const [pendingUrl, setPendingUrl] = useState("")
  const [saving, setSaving] = useState(false)

  const addUrl = (): void => {
    const value = pendingUrl.trim()
    if (!value) {
      return
    }
    setFiles((prev) => [...prev, value])
    setPendingUrl("")
  }

  const save = async (): Promise<void> => {
    setSaving(true)
    try {
      await onSave(files)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">Evidence Upload ({requestId})</p>
      <div className="mt-3 flex gap-2">
        <Input
          type="url"
          placeholder="Paste evidence URL"
          value={pendingUrl}
          onChange={(event) => setPendingUrl(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              addUrl()
            }
          }}
        />
        <Button type="button" variant="outline" onClick={addUrl}>
          Add
        </Button>
        <Button type="button" variant="outline" onClick={() => void save()} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
      <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
        {files.map((file, index) => (
          <li key={`${file}-${index}`}>
            <a className="text-blue-400 underline" href={file} target="_blank" rel="noreferrer">
              {file}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
