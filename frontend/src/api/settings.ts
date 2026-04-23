export interface SettingsResponse {
  gemini_api_key_set: boolean
  groq_api_key_set: boolean

  gemini_model: string
  groq_model: string

  scrape_schedule_time: string
  scrape_location: string
  scrape_max_results: number
  scrape_headless: boolean
  scrape_user_agent: string

  outreach_send_enabled: boolean
  outreach_sender_name: string
  outreach_sender_email: string
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_use_tls: boolean
  smtp_password_set: boolean
}

export interface SettingsUpdateRequest {
  gemini_api_key?: string
  groq_api_key?: string

  gemini_model?: string
  groq_model?: string

  scrape_schedule_time?: string
  scrape_location?: string
  scrape_max_results?: number
  scrape_headless?: boolean
  scrape_user_agent?: string

  outreach_send_enabled?: boolean
  outreach_sender_name?: string
  outreach_sender_email?: string
  smtp_host?: string
  smtp_port?: number
  smtp_username?: string
  smtp_password?: string
  smtp_use_tls?: boolean
}

export interface OutreachPolicyResponse {
  outreach_enabled: boolean
  outreach_daily_send_cap: number
  outreach_send_window_start: string
  outreach_send_window_end: string
  outreach_send_timezone: string
  outreach_enforce_window: boolean
  outreach_enforce_daily_cap: boolean
  outreach_enforce_suppression: boolean
  outreach_allowed_statuses: string[]
}

export interface OutreachPolicyUpdateRequest {
  outreach_enabled?: boolean
  outreach_daily_send_cap?: number
  outreach_send_window_start?: string
  outreach_send_window_end?: string
  outreach_send_timezone?: string
  outreach_enforce_window?: boolean
  outreach_enforce_daily_cap?: boolean
  outreach_enforce_suppression?: boolean
  outreach_allowed_statuses?: string[]
}

export interface OutreachUsageTodayResponse {
  timezone: string
  sent_today: number
  daily_cap: number
}

export interface SuppressionItem {
  id: number
  email: string
  reason: string | null
  created_at: string
}

export interface SuppressionAddRequest {
  email: string
  reason?: string
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchSettings(): Promise<SettingsResponse> {
  return apiRequest<SettingsResponse>('/settings')
}

export async function updateSettings(data: SettingsUpdateRequest): Promise<SettingsResponse> {
  return apiRequest<SettingsResponse>('/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function fetchOutreachPolicy(): Promise<OutreachPolicyResponse> {
  return apiRequest<OutreachPolicyResponse>('/settings/outreach-policy')
}

export async function updateOutreachPolicy(
  data: OutreachPolicyUpdateRequest,
): Promise<OutreachPolicyResponse> {
  return apiRequest<OutreachPolicyResponse>('/settings/outreach-policy', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function fetchOutreachUsageToday(): Promise<OutreachUsageTodayResponse> {
  return apiRequest<OutreachUsageTodayResponse>('/settings/outreach-policy/usage-today')
}

export async function fetchSuppressions(q?: string): Promise<SuppressionItem[]> {
  const params = new URLSearchParams()
  if (q?.trim()) params.set('q', q.trim())
  return apiRequest<SuppressionItem[]>(
    `/settings/outreach-suppressions${params.toString() ? `?${params.toString()}` : ''}`,
  )
}

export async function addSuppression(data: SuppressionAddRequest): Promise<SuppressionItem> {
  return apiRequest<SuppressionItem>('/settings/outreach-suppressions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function deleteSuppression(id: number): Promise<void> {
  await apiRequest(`/settings/outreach-suppressions/${id}`, { method: 'DELETE' })
}

