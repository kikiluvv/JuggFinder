# Phase 12 — Frontend Core Components

## Goal
Build the stats bar, lead table with sorting/filtering/search, and the filter panel. This is the primary view the user sees — it must be functionally complete and visually clean before moving to panels.

## Completion Criteria
- [ ] Stats bar shows Total, New Today, Avg Score, and Scraping indicator (polls `/scrape/status` every 5s)
- [ ] Lead table renders with all 6 columns
- [ ] Default sort: Score descending
- [ ] Column headers are clickable to sort asc/desc
- [ ] All filter controls work: Category (multi-select), Status (multi-select), Score range slider, Has Website dropdown
- [ ] Search input debounced 300ms, filters by name or address
- [ ] Color-coded rows by status (indigo for `new`, green for `interested`, muted for `archived`)
- [ ] Archived leads hidden by default; shown via a toggle
- [ ] Pagination at 50 leads per page
- [ ] TanStack Table manages column sorting and table state

---

## Component Tree

```
App.tsx
└── Dashboard.tsx
    ├── TopNav.tsx             — logo, "Scrape Now" button, settings icon
    ├── StatsBar.tsx           — Total | New Today | Avg Score | Scraping indicator
    ├── FilterBar.tsx          — search + all filter controls + Clear button
    └── LeadTable.tsx          — TanStack Table + paginated rows
        └── LeadRow.tsx        — single row, color-coded by status
```

---

## `StatsBar.tsx`

- Fetch stats with `useQuery({ queryKey: ['stats'], queryFn: fetchStats, refetchInterval: 30_000 })`
- Fetch scrape status with `useQuery({ queryKey: ['scrapeStatus'], queryFn: fetchScrapeStatus, refetchInterval: 5_000 })`
- Scraping indicator: animated pulsing dot + "Scraping..." text, only shown when `running === true`

---

## `FilterBar.tsx`

Maintain all filter state in the parent `Dashboard.tsx` (or a custom `useFilters` hook) and pass down as props.

Filter state shape:
```typescript
interface Filters {
  search: string
  categories: string[]
  statuses: LeadStatus[]
  scoreMin: number
  scoreMax: number
  hasWebsite: 'all' | 'yes' | 'no' | 'social'
  showArchived: boolean
}
```

Default values: `scoreMin=5`, `scoreMax=10`, `statuses=['new','reviewed','interested']`, `showArchived=false`

---

## `LeadTable.tsx`

Use TanStack Table (`useReactTable`) for column definitions and sorting state.

```typescript
import { useReactTable, getCoreRowModel, getSortedRowModel } from '@tanstack/react-table'
```

Column definitions:
```typescript
const columns = [
  columnHelper.accessor('lead_score', { header: 'Score', cell: ScoreBadge }),
  columnHelper.accessor('name', { header: 'Business' }),
  columnHelper.accessor('category', { header: 'Category' }),
  columnHelper.accessor('website_url', { header: 'Website', enableSorting: false }),
  columnHelper.accessor('status', { header: 'Status', cell: StatusBadge }),
  columnHelper.accessor('created_at', { header: 'Date Found' }),
]
```

Pass filter params to `useQuery` so the backend handles filtering and pagination (not client-side):
```typescript
useQuery({
  queryKey: ['leads', filters, page],
  queryFn: () => fetchLeads({ ...filters, page }),
  keepPreviousData: true,
})
```

---

## Row Color Coding

Apply Tailwind classes to each row based on status:

```typescript
const rowClass = {
  new:        'border-l-4 border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30',
  interested: 'border-l-4 border-green-500 bg-green-50 dark:bg-green-950/30',
  reviewed:   '',
  archived:   'opacity-50 text-gray-400',
}[lead.status] ?? ''
```

---

## Score Badge Colors

```typescript
const scoreBadgeVariant = (score: number) =>
  score >= 8 ? 'destructive' :   // red — no/broken website (great lead)
  score >= 5 ? 'warning' :       // yellow — has issues
  'secondary'                    // grey — decent site (weak lead)
```

Note: shadcn/ui `Badge` doesn't have a `warning` variant by default — extend it or use a className override.

---

## Done When
The full lead table renders with real data from the backend, all filters work, clicking a column header sorts it, and the stats bar updates with live scrape status.
