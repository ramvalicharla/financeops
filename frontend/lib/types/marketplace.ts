export type MarketplaceTemplateStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "rejected"
  | "archived"

export interface MarketplaceContributor {
  id: string
  tenant_id: string
  display_name: string
  bio: string | null
  contributor_tier: "community" | "verified_partner" | "platform_official"
  revenue_share_pct: string
  total_earnings: string
  total_templates: number
  total_downloads: number
  rating_average: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MarketplaceTemplate {
  id: string
  contributor_id: string
  tenant_id: string
  title: string
  description: string
  template_type: string
  industry: string | null
  price_credits: number
  is_free: boolean
  template_data: Record<string, unknown>
  preview_image_url: string | null
  tags: string[]
  download_count: number
  rating_count: number
  rating_sum: number
  rating_average: string
  status: MarketplaceTemplateStatus
  review_notes: string | null
  is_featured: boolean
  created_at: string
  updated_at: string
  contributor?: MarketplaceContributor
}

export interface MarketplaceRating {
  id: string
  template_id: string
  buyer_tenant_id: string
  rating: number
  review_text: string | null
  created_at: string
}

export interface MarketplacePurchase {
  id: string
  template_id: string
  buyer_tenant_id: string
  contributor_id: string
  price_credits_paid: number
  platform_share_credits: number
  contributor_share_credits: number
  platform_share_pct: string
  contributor_share_pct: string
  status: string
  purchased_at: string
}

export interface MarketplacePayout {
  id: string
  contributor_id: string
  period_start: string
  period_end: string
  total_credits_earned: number
  total_usd_amount: string
  status: string
  created_at: string
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  limit: number
  offset: number
}

