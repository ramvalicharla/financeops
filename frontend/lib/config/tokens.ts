export type DisplayScale =
  | "INR"
  | "LAKHS"
  | "CRORES"
  | "THOUSANDS"
  | "MILLIONS"
  | "BILLIONS"

export const STATUS_COLORS = {
  pending: "bg-yellow-500/20 text-yellow-300",
  running: "bg-blue-500/20 text-blue-300",
  complete: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  completed:
    "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  failed: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
  error: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
  success: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  warning:
    "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  active: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  locked:
    "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  draft: "bg-muted text-muted-foreground",
  inactive: "bg-muted text-muted-foreground",
  default: "bg-muted text-muted-foreground",
} as const

export type StatusKey = keyof typeof STATUS_COLORS

export const CHART_COLORS = [
  "#60A5FA",
  "#14B8A6",
  "#F59E0B",
  "#A78BFA",
  "#FB7185",
  "#34D399",
  "#F87171",
  "#94A3B8",
  "#2DD4BF",
  "#FBBF24",
] as const

export const SCALE_DIVISORS = {
  INR: 1,
  LAKHS: 100_000,
  CRORES: 10_000_000,
  THOUSANDS: 1_000,
  MILLIONS: 1_000_000,
  BILLIONS: 1_000_000_000,
} as const satisfies Record<DisplayScale, number>

export const SCALE_LABELS = {
  INR: "",
  LAKHS: "L",
  CRORES: "Cr",
  THOUSANDS: "K",
  MILLIONS: "M",
  BILLIONS: "B",
} as const satisfies Record<DisplayScale, string>

export const SCALE_FULL_LABELS = {
  INR: "in \u20b9",
  LAKHS: "\u20b9 in Lakhs",
  CRORES: "\u20b9 in Crores",
  THOUSANDS: "in Thousands",
  MILLIONS: "in Millions",
  BILLIONS: "in Billions",
} as const satisfies Record<DisplayScale, string>

export const SCALE_DECIMAL_PLACES = {
  INR: 2,
  LAKHS: 2,
  CRORES: 2,
  THOUSANDS: 2,
  MILLIONS: 2,
  BILLIONS: 3,
} as const satisfies Record<DisplayScale, number>

export interface ScaleOption {
  value: DisplayScale
  label: string
  group: "Indian" | "International"
}

export const SCALE_OPTIONS = [
  { value: "INR", label: "\u20b9 (Full Rupees)", group: "Indian" },
  { value: "LAKHS", label: "\u20b9 Lakhs", group: "Indian" },
  { value: "CRORES", label: "\u20b9 Crores", group: "Indian" },
  { value: "THOUSANDS", label: "Thousands (K)", group: "International" },
  { value: "MILLIONS", label: "Millions (M)", group: "International" },
  { value: "BILLIONS", label: "Billions (B)", group: "International" },
] as const satisfies readonly ScaleOption[]
