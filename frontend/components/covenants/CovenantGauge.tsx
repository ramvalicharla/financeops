"use client"

export type CovenantGaugeProps = {
  actual: number
  threshold: number
  direction: "above" | "below"
  status: "pass" | "near_breach" | "breach"
  actualLabel?: string
  thresholdLabel?: string
}

export function CovenantGauge({
  actual,
  threshold,
  direction,
  status,
  actualLabel,
  thresholdLabel,
}: CovenantGaugeProps) {
  const safeActual = Number.isFinite(actual) && actual > 0 ? actual : 0
  const safeThreshold = Number.isFinite(threshold) && threshold > 0 ? threshold : 1
  const ratio = direction === "below" ? safeActual / safeThreshold : safeThreshold / safeActual
  const clamped = Math.max(0, Math.min(ratio, 1.5))
  const angle = clamped * 180
  const color =
    status === "pass" ? "#22c55e" : status === "near_breach" ? "#f59e0b" : "#ef4444"

  const r = 60
  const cx = 80
  const cy = 80
  const rad = ((angle - 180) * Math.PI) / 180
  const endX = cx + r * Math.cos(rad)
  const endY = cy + r * Math.sin(rad)
  const large = angle > 180 ? 1 : 0

  return (
    <svg width="160" height="90" viewBox="0 0 160 90">
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="#374151"
        strokeWidth="12"
        strokeLinecap="round"
      />
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${large} 1 ${endX} ${endY}`}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeLinecap="round"
      />
      <line
        x1={cx}
        y1={cy - r - 6}
        x2={cx}
        y2={cy - r + 6}
        stroke="#9ca3af"
        strokeWidth="2"
      />
      <text x={cx} y={cy + 16} textAnchor="middle" fill="white" fontSize="14" fontWeight="600">
        {actualLabel ?? safeActual.toFixed(2)}
      </text>
      <text x={cx} y={cy + 30} textAnchor="middle" fill="#9ca3af" fontSize="10">
        threshold: {thresholdLabel ?? safeThreshold.toFixed(2)}
      </text>
    </svg>
  )
}
