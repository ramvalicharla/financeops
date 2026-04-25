import Link from "next/link"

// TODO: promote #185FA5 to a --brand-finqor CSS token in a future polish FU
export function BrandMark() {
  return (
    <Link
      href="/dashboard"
      aria-label="Finqor"
      className="flex shrink-0 items-center gap-2 rounded-sm"
    >
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect width="28" height="28" rx="6" fill="#185FA5" />
        {/* F lettermark: vertical stem + top crossbar + middle crossbar */}
        <rect x="8" y="7" width="3" height="14" fill="white" />
        <rect x="8" y="7" width="12" height="3" fill="white" />
        <rect x="8" y="13" width="9" height="3" fill="white" />
      </svg>
      <span className="hidden text-sm font-semibold tracking-tight text-muted-foreground md:inline">
        finqor
      </span>
    </Link>
  )
}
