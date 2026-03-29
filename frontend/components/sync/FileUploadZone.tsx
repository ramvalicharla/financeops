"use client"

import { useMemo } from "react"
import { UploadCloud, X } from "lucide-react"
import { useDropzone } from "react-dropzone"
import { cn } from "@/lib/utils"

interface FileUploadZoneProps {
  file: File | null
  onFileSelected: (file: File | null) => void
  error: string | null
}

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
const accept = {
  "text/csv": [".csv"],
  "application/json": [".json"],
  "application/xml": [".xml"],
  "text/xml": [".xml"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileUploadZone({ file, onFileSelected, error }: FileUploadZoneProps) {
  const {
    getRootProps,
    getInputProps,
    isDragActive,
    fileRejections,
  } = useDropzone({
    accept,
    maxSize: MAX_FILE_SIZE_BYTES,
    multiple: false,
    onDropAccepted: (files) => {
      onFileSelected(files[0] ?? null)
    },
    onDropRejected: () => {
      onFileSelected(null)
    },
  })

  const rejectionMessage = useMemo(() => {
    const rejection = fileRejections[0]
    if (!rejection) {
      return null
    }
    const code = rejection.errors[0]?.code
    if (code === "file-too-large") {
      return "File is too large. Maximum size is 50 MB."
    }
    return "Unsupported file type. Use CSV, XML, JSON, or XLSX."
  }, [fileRejections])

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition",
          isDragActive
            ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.1)]"
            : "border-border hover:border-[hsl(var(--brand-primary)/0.5)]",
        )}
      >
        <input {...getInputProps()} />
        <UploadCloud className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">
          {isDragActive ? "Drop to upload" : "Drop file here or click to browse"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          CSV, XML, JSON, XLSX (max 50MB)
        </p>
      </div>

      {file ? (
        <div className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2">
          <div>
            <p className="text-sm font-medium text-foreground">{file.name}</p>
            <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
          </div>
          <button
            aria-label="Remove file"
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={() => onFileSelected(null)}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      {error || rejectionMessage ? (
        <p className="text-sm text-destructive">{error ?? rejectionMessage}</p>
      ) : null}
    </div>
  )
}
