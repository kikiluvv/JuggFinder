import type { LeadDetail, LeadsResponse, OutreachDraftResponse, StatsResponse } from '@/types'

export interface LeadsParams {
  search?: string
  category?: string[]
  status?: string[]
  score_min?: number
  score_max?: number
  has_website?: 'all' | 'yes' | 'no' | 'social'
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

function buildQuery(params: LeadsParams): string {
  const q = new URLSearchParams()
  if (params.search) q.set('search', params.search)
  if (params.category?.length) params.category.forEach((c) => q.append('category', c))
  if (params.status?.length) params.status.forEach((s) => q.append('status', s))
  if (params.score_min != null) q.set('score_min', String(params.score_min))
  if (params.score_max != null) q.set('score_max', String(params.score_max))
  if (params.has_website) q.set('has_website', params.has_website)
  if (params.sort_by) q.set('sort_by', params.sort_by)
  if (params.sort_dir) q.set('sort_dir', params.sort_dir)
  if (params.page) q.set('page', String(params.page))
  if (params.page_size) q.set('page_size', String(params.page_size))
  return q.toString()
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchLeads(params: LeadsParams = {}): Promise<LeadsResponse> {
  const qs = buildQuery(params)
  return apiRequest<LeadsResponse>(`/leads${qs ? `?${qs}` : ''}`)
}

export async function fetchLead(id: number): Promise<LeadDetail> {
  return apiRequest<LeadDetail>(`/leads/${id}`)
}

export async function updateLead(
  id: number,
  data: { status?: string; notes?: string; outreach_draft?: string },
): Promise<LeadDetail> {
  return apiRequest<LeadDetail>(`/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function deleteLead(id: number): Promise<void> {
  await apiRequest(`/leads/${id}`, { method: 'DELETE' })
}

export async function fetchStats(): Promise<StatsResponse> {
  return apiRequest<StatsResponse>('/leads/stats')
}

export async function rescanLead(id: number): Promise<LeadDetail> {
  return apiRequest<LeadDetail>(`/leads/${id}/rescan`, { method: 'POST' })
}

export async function draftOutreach(id: number): Promise<OutreachDraftResponse> {
  return apiRequest<OutreachDraftResponse>(`/leads/${id}/draft-outreach`, { method: 'POST' })
}

/**
 * Triggers a file download of the CSV export. Respects the current filter
 * params so the user gets exactly what they see in the table.
 */
export function exportLeadsCsvUrl(params: LeadsParams = {}): string {
  const qs = buildQuery(params)
  return `/api/leads/export.csv${qs ? `?${qs}` : ''}`
}
