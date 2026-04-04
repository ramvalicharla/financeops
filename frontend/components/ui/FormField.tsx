"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Props for the shared accessible form field wrapper.
 */
export interface FormFieldProps {
  /** Required field id used to connect the label, input, hint, and error text. */
  id: string
  /** Always-visible label text for the field. */
  label: string
  /** Optional error message shown below the field. */
  error?: string
  /** Optional hint text shown below the field. */
  hint?: string
  /** Marks the field as required visually and for assistive technology. */
  required?: boolean
  /** The input, select, or textarea element rendered inside the field. */
  children: React.ReactNode
}

type FieldControlProps = {
  id?: string
  className?: string
  "aria-invalid"?: boolean | "true" | "false"
  "aria-describedby"?: string
  "aria-required"?: boolean | "true" | "false"
}

/**
 * Wraps a form control with a persistent label, optional hint text, and optional error text.
 */
export function FormField({
  id,
  label,
  error,
  hint,
  required = false,
  children,
}: FormFieldProps) {
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint ? hintId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ")

  let control = children

  if (React.isValidElement(children)) {
    const child = children as React.ReactElement<FieldControlProps>
    const existingClassName = child.props.className
    const existingDescribedBy = child.props["aria-describedby"]

    control = React.cloneElement(child, {
      id,
      className: cn(
        existingClassName,
        error && "border-[hsl(var(--brand-danger))] focus-visible:ring-[hsl(var(--brand-danger))]",
      ),
      "aria-invalid": error ? "true" : child.props["aria-invalid"],
      "aria-describedby": [existingDescribedBy, describedBy].filter(Boolean).join(" ") || undefined,
      "aria-required": required ? "true" : child.props["aria-required"],
    })
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground" htmlFor={id}>
        {label}
        {required ? (
          <span aria-hidden="true" className="ml-1 text-[hsl(var(--brand-danger))]">
            *
          </span>
        ) : null}
      </label>
      {control}
      {hint ? (
        <p id={hintId} className="text-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-sm text-[hsl(var(--brand-danger))]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
