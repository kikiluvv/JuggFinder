import type { ScrapeStatus } from '@/types'

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function startScrape(categories: string[]): Promise<{ ok: boolean; message: string }> {
  return apiRequest('/scrape/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ categories }),
  })
}

export async function fetchScrapeStatus(): Promise<ScrapeStatus> {
  return apiRequest<ScrapeStatus>('/scrape/status')
}

export async function fetchCategories(): Promise<{ categories: string[] }> {
  return apiRequest<{ categories: string[] }>('/categories')
}
