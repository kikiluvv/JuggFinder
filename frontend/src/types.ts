export type LeadStatus = 'new' | 'reviewed' | 'interested' | 'archived'

export interface LeadSummary {
  id: number
  name: string
  category: string | null
  lead_score: number
  opportunity_score: number | null
  website_url: string | null
  email: string | null
  phone: string | null
  status: LeadStatus
  created_at: string
}

export interface LeadDetail extends LeadSummary {
  address: string | null
  rating: number | null
  review_count: number | null
  hours: string | null
  google_categories: string[]
  business_description: string | null
  photo_count: number | null
  is_claimed: boolean | null
  has_ssl: boolean | null
  has_mobile_viewport: boolean | null
  website_status_code: number | null
  copyright_year: number | null
  tech_stack: string[]
  ai_score: number | null
  ai_issues: string[]
  ai_summary: string | null
  outreach_draft: string | null
  notes: string | null
  updated_at: string
  last_scanned_at: string | null
}

export interface LeadsResponse {
  leads: LeadSummary[]
  total: number
  page: number
  pages: number
}

export interface StatsResponse {
  total: number
  new_today: number
  avg_score: number
}

export interface SelectorHealth {
  cards_found?: number
  names_extracted?: number
  addresses_extracted?: number
  phones_extracted?: number
  websites_extracted?: number
  ratings_extracted?: number
  reviews_extracted?: number
  categories_extracted?: number
  hours_extracted?: number
  descriptions_extracted?: number
  captchas_encountered?: number
  failures?: string[]
}

export interface ScrapeStatus {
  running: boolean
  started_at: string | null
  categories: string[]
  current_category: string | null
  categories_done: number
  categories_total: number
  businesses_processed: number
  new_leads: number
  selector_health: SelectorHealth
  error: string | null
}

export interface OutreachDraftResponse {
  lead_id: number
  draft: string
}
