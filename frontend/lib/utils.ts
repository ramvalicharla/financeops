import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import {
  SCALE_DECIMAL_PLACES,
  SCALE_DIVISORS,
  SCALE_FULL_LABELS,
  SCALE_LABELS,
  SCALE_OPTIONS,
  type DisplayScale,
} from "@/lib/config/tokens"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const sanitizeDecimalString = (value: string): string => {
  const trimmed = value.trim()
  if (!trimmed) {
    return "0"
  }
  const cleaned = trimmed.replace(/[^0-9.-]/g, "")
  if (!cleaned || cleaned === "-" || cleaned === "." || cleaned === "-.") {
    return "0"
  }
  const sign = cleaned.startsWith("-") ? "-" : ""
  const unsigned = cleaned.replace(/-/g, "")
  const [integerRaw, decimalRaw = ""] = unsigned.split(".")
  const integerPart = (integerRaw || "0").replace(/^0+(?=\d)/, "") || "0"
  const decimalPart = decimalRaw.replace(/\./g, "")
  return `${sign}${integerPart}${decimalPart ? `.${decimalPart}` : ""}`
}

// ============================================================
// DISPLAY SCALE - Amount formatting for Indian and international
// ============================================================

export type { DisplayScale } from "@/lib/config/tokens"
export {
  SCALE_DECIMAL_PLACES,
  SCALE_DIVISORS,
  SCALE_FULL_LABELS,
  SCALE_LABELS,
  SCALE_OPTIONS,
} from "@/lib/config/tokens"

/**
 * Format a financial amount for display.
 * NOTE: Input must be full stored value (not pre-scaled).
 * This is the SINGLE source of truth for amount formatting.
 */
export function formatAmount(
  amount: number | string | null | undefined,
  scale: DisplayScale = "LAKHS",
  currency: string = "\u20b9",
  options: {
    showLabel?: boolean
    showCurrency?: boolean
    decimalPlaces?: number
    compact?: boolean
  } = {},
): string {
  const {
    showLabel = true,
    showCurrency = true,
    decimalPlaces,
  } = options

  if (amount === null || amount === undefined || amount === "") {
    return showCurrency ? `${currency}-` : "-"
  }

  const num = typeof amount === "string" ? Number.parseFloat(amount) : amount
  if (Number.isNaN(num)) return showCurrency ? `${currency}-` : "-"

  const divisor = SCALE_DIVISORS[scale]
  const places = decimalPlaces ?? SCALE_DECIMAL_PLACES[scale]
  const scaled = num / divisor

  let formatted: string

  if (scale === "INR") {
    formatted = formatIndianNumber(scaled, places)
  } else {
    formatted = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: places,
      maximumFractionDigits: places,
    }).format(scaled)
  }

  const label = showLabel ? SCALE_LABELS[scale] : ""
  const sym = showCurrency ? currency : ""

  return `${sym}${formatted}${label}`
}

/**
 * Format number in Indian comma system.
 * 1,23,45,678.00 (not 12,345,678.00)
 */
export function formatIndianNumber(
  amount: number,
  decimalPlaces: number = 2,
): string {
  const fixed = Math.abs(amount).toFixed(decimalPlaces)
  const [intPart, decPart] = fixed.split(".")

  let result: string
  if (intPart.length <= 3) {
    result = intPart
  } else {
    result = intPart.slice(-3)
    let remaining = intPart.slice(0, -3)
    while (remaining.length > 0) {
      result = `${remaining.slice(-2)},${result}`
      remaining = remaining.slice(0, -2)
    }
  }

  const formatted = decimalPlaces > 0
    ? `${result}.${decPart}`
    : result

  return amount < 0 ? `-${formatted}` : formatted
}

/**
 * Parse a displayed amount back to raw value using selected scale.
 */
export function parseDisplayAmountToRaw(
  displayValue: string,
  scale: DisplayScale,
): number | null {
  const clean = displayValue.replace(/,/g, "").trim()
  if (!clean) {
    return null
  }
  const parsed = Number.parseFloat(clean)
  if (Number.isNaN(parsed)) {
    return null
  }
  return parsed * SCALE_DIVISORS[scale]
}

/**
 * Format a ratio/percentage (not scaled by display scale).
 */
export function formatPercent(
  value: number | string | null | undefined,
  decimalPlaces: number = 2,
): string {
  if (value === null || value === undefined || value === "") return "-"
  const num = typeof value === "string" ? Number.parseFloat(value) : value
  if (Number.isNaN(num)) return "-"
  const pct = num <= 1 && num >= -1 ? num * 100 : num
  return `${pct.toFixed(decimalPlaces)}%`
}

/**
 * Format a ratio (e.g. 5.00x for debt/EBITDA)
 */
export function formatRatio(
  value: number | string | null | undefined,
  decimalPlaces: number = 2,
  suffix: string = "x",
): string {
  if (value === null || value === undefined || value === "") return "-"
  const num = typeof value === "string" ? Number.parseFloat(value) : value
  if (Number.isNaN(num)) return "-"
  return `${num.toFixed(decimalPlaces)}${suffix}`
}

/**
 * Get scale label for report header.
 */
export function getScaleHeaderLabel(scale: DisplayScale): string {
  return SCALE_FULL_LABELS[scale]
}

// Backward-compatible wrappers
const parseLegacyNumber = (value: string): number => {
  const normalized = sanitizeDecimalString(value)
  const parsed = Number.parseFloat(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

export function formatINR(value: string): string {
  return formatAmount(parseLegacyNumber(value), "INR", "\u20b9", {
    showLabel: false,
    showCurrency: true,
  })
}

export function isZeroDecimal(value: string): boolean {
  const normalized = sanitizeDecimalString(value).replace("-", "")
  const [integerPart = "0", decimalPart = ""] = normalized.split(".")
  const integerZero = /^0+$/.test(integerPart || "0")
  const decimalZero = !decimalPart || /^0+$/.test(decimalPart)
  return integerZero && decimalZero
}

export function decimalStringToNumber(value: string): number {
  return parseLegacyNumber(value)
}

export function formatINRCompact(value: string): string {
  const absolute = Math.abs(parseLegacyNumber(value))
  if (absolute >= 10000000) {
    return `\u20b9${(absolute / 10000000).toFixed(1)}Cr`
  }
  if (absolute >= 100000) {
    return `\u20b9${(absolute / 100000).toFixed(1)}L`
  }
  if (absolute >= 1000) {
    return `\u20b9${(absolute / 1000).toFixed(1)}K`
  }
  return formatINR(value)
}
