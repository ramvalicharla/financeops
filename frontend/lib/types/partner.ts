export interface PartnerProfile {
  id: string
  tenant_id: string
  partner_tier: "referral" | "reseller" | "technology"
  company_name: string
  contact_email: string
  website_url: string | null
  partner_code: string
  commission_rate_pct: string
  total_referrals: number
  total_commissions_earned: string
  is_active: boolean
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface ReferralTrackingRow {
  id: string
  partner_id: string
  referred_tenant_id: string | null
  tenant_id: string
  referral_code: string
  referral_email: string | null
  status: "clicked" | "signed_up" | "converted" | "churned" | "expired"
  clicked_at: string
  signed_up_at: string | null
  converted_at: string | null
  first_payment_amount: string | null
  expires_at: string
  created_at: string
  updated_at: string
}

export interface PartnerCommissionRow {
  id: string
  partner_id: string
  referral_id: string
  referred_tenant_id: string
  commission_type: "first_payment" | "recurring" | "technology_rev_share"
  payment_amount: string
  commission_rate: string
  commission_amount: string
  status: "pending" | "approved" | "paid" | "cancelled"
  period: string | null
  created_at: string
}

export interface PartnerDashboard {
  partner: PartnerProfile
  referral_link: string
  stats: {
    total_clicks: number
    total_signups: number
    total_conversions: number
    conversion_rate: string
    total_commissions_earned: string
    pending_commissions: string
  }
  recent_referrals: ReferralTrackingRow[]
  commission_history: PartnerCommissionRow[]
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

