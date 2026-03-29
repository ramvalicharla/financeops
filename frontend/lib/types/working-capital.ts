export interface WCSnapshot {
  id: string
  tenant_id: string
  period: string
  entity_id: string | null
  snapshot_date: string
  ar_total: string
  ar_current: string
  ar_30: string
  ar_60: string
  ar_90: string
  dso_days: string
  ap_total: string
  ap_current: string
  ap_30: string
  ap_60: string
  ap_90: string
  dpo_days: string
  inventory_days: string
  ccc_days: string
  net_working_capital: string
  current_ratio: string
  quick_ratio: string
}

export interface WCTrendPoint {
  period: string
  dso_days: string
  dpo_days: string
  ccc_days: string
  net_working_capital: string
}

export interface WCARItem {
  id: string
  customer_name: string
  amount: string
  days_overdue: number
  aging_bucket: string
  payment_probability_score: string | null
}

export interface WCAPItem {
  id: string
  vendor_name: string
  amount: string
  days_overdue: number
  aging_bucket: string
  early_payment_discount_available: boolean
  early_payment_discount_pct: string | null
}

export interface WCDashboardPayload {
  current_snapshot: WCSnapshot
  trends: WCTrendPoint[]
  top_overdue_ar: WCARItem[]
  discount_opportunities: Array<WCAPItem & { saving_inr: string }>
  mom_changes: {
    dso: string
    dpo: string
    ccc: string
    nwc: string
  }
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}
