import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { exportLeadsCsvUrl } from '@/api/leads'
import { fetchCategories } from '@/api/scrape'
import type { Filters } from '@/hooks/useFilters'
import type { LeadStatus } from '@/types'

const STATUS_OPTIONS: { value: LeadStatus; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'interested', label: 'Interested' },
]

interface FilterBarProps {
  filters: Filters
  onChange: (f: Partial<Filters>) => void
  onReset: () => void
}

export default function FilterBar({ filters, onChange, onReset }: FilterBarProps) {
  const { data: catData } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    staleTime: Infinity,
  })
  const categories = catData?.categories ?? []

  function toggleCategory(cat: string, checked: boolean) {
    const next = checked
      ? [...filters.categories, cat]
      : filters.categories.filter((c) => c !== cat)
    onChange({ categories: next })
  }

  function toggleStatus(s: LeadStatus, checked: boolean) {
    const next = checked ? [...filters.statuses, s] : filters.statuses.filter((x) => x !== s)
    onChange({ statuses: next })
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-5">
      {/* Search */}
      <div>
        <Label className="text-xs text-gray-500 uppercase tracking-wide mb-1.5 block">Search</Label>
        <input
          type="text"
          placeholder="Business name or address…"
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {/* Score range */}
      <div>
        <Label className="text-xs text-gray-500 uppercase tracking-wide mb-1.5 block">
          Score: {filters.scoreMin}–{filters.scoreMax}
        </Label>
        <Slider
          min={1}
          max={10}
          step={1}
          value={[filters.scoreMin, filters.scoreMax] as [number, number]}
          onValueChange={(vals) => {
            const [min, max] = vals as [number, number]
            onChange({ scoreMin: min, scoreMax: max })
          }}
          className="mt-2"
        />
      </div>

      {/* Statuses */}
      <div>
        <Label className="text-xs text-gray-500 uppercase tracking-wide mb-1.5 block">Status</Label>
        <div className="flex flex-wrap gap-3">
          {STATUS_OPTIONS.map(({ value, label }) => (
            <div key={value} className="flex items-center gap-1.5">
              <Checkbox
                id={`status-${value}`}
                checked={filters.statuses.includes(value)}
                onCheckedChange={(c) => toggleStatus(value, !!c)}
              />
              <label htmlFor={`status-${value}`} className="text-sm cursor-pointer">
                {label}
              </label>
            </div>
          ))}
          <div className="flex items-center gap-1.5">
            <Checkbox
              id="show-archived"
              checked={filters.showArchived}
              onCheckedChange={(c) => onChange({ showArchived: !!c })}
            />
            <label htmlFor="show-archived" className="text-sm cursor-pointer text-gray-400">
              Archived
            </label>
          </div>
        </div>
      </div>

      {/* Has website */}
      <div>
        <Label className="text-xs text-gray-500 uppercase tracking-wide mb-1.5 block">
          Website
        </Label>
        <Select
          value={filters.hasWebsite}
          onValueChange={(v) => onChange({ hasWebsite: v as Filters['hasWebsite'] })}
        >
          <SelectTrigger className="w-36 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="yes">Has website</SelectItem>
            <SelectItem value="no">No website</SelectItem>
            <SelectItem value="social">Social only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div>
          <Label className="text-xs text-gray-500 uppercase tracking-wide mb-1.5 block">
            Categories
          </Label>
          <div className="flex flex-wrap gap-3">
            {categories.map((cat) => (
              <div key={cat} className="flex items-center gap-1.5">
                <Checkbox
                  id={`cat-${cat}`}
                  checked={filters.categories.includes(cat)}
                  onCheckedChange={(c) => toggleCategory(cat, !!c)}
                />
                <label htmlFor={`cat-${cat}`} className="text-sm capitalize cursor-pointer">
                  {cat}
                </label>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <button
          onClick={onReset}
          className="text-sm text-indigo-600 hover:underline focus:outline-none"
        >
          Clear filters
        </button>
        <a
          href={exportLeadsCsvUrl({
            search: filters.search || undefined,
            category: filters.categories,
            status: filters.showArchived
              ? [...filters.statuses, 'archived']
              : filters.statuses,
            score_min: filters.scoreMin,
            score_max: filters.scoreMax,
            has_website: filters.hasWebsite,
          })}
          className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-indigo-600 hover:underline"
          download
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </a>
      </div>
    </div>
  )
}
