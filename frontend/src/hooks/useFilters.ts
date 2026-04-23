import { useState } from 'react'
import type { LeadStatus } from '@/types'

export interface Filters {
  search: string
  categories: string[]
  statuses: LeadStatus[]
  scoreMin: number
  scoreMax: number
  hasWebsite: 'all' | 'yes' | 'no' | 'social'
  showArchived: boolean
}

// Default to score 5+ to hide "well-established business" (score 1) and
// lightly-flawed sites (score 2-4) — matches the payout-focused mission.
// Toggle the slider to see the full range.
export const DEFAULT_FILTERS: Filters = {
  search: '',
  categories: [],
  statuses: ['new', 'reviewed', 'interested'],
  scoreMin: 5,
  scoreMax: 10,
  hasWebsite: 'all',
  showArchived: false,
}

export function useFilters() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)

  function onChange(patch: Partial<Filters>) {
    setFilters((prev) => ({ ...prev, ...patch }))
  }

  function onReset() {
    setFilters(DEFAULT_FILTERS)
  }

  return { filters, onChange, onReset }
}
