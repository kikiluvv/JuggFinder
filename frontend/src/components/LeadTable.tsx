import { fetchLeads } from '@/api/leads'
import { Badge } from '@/components/ui/badge'
import type { Filters } from '@/hooks/useFilters'
import type { LeadSummary } from '@/types'
import { useQuery } from '@tanstack/react-query'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { ChevronDown, ChevronUp, ChevronsUpDown, ExternalLink } from 'lucide-react'
import { useState } from 'react'

const SCORE_COLORS: Record<string, string> = {
  high: 'bg-red-100 text-red-700 border-red-200',
  mid: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200',
}

function scoreBadgeClass(score: number): string {
  if (score >= 8) return SCORE_COLORS.high
  if (score >= 5) return SCORE_COLORS.mid
  return SCORE_COLORS.low
}

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  reviewed: 'Reviewed',
  interested: 'Interested',
  archived: 'Archived',
}

const STATUS_CLASS: Record<string, string> = {
  new: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  interested: 'bg-green-100 text-green-700 border-green-200',
  reviewed: 'bg-gray-100 text-gray-600 border-gray-200',
  archived: 'bg-gray-50 text-gray-400 border-gray-100',
}

const ROW_CLASS: Record<string, string> = {
  new: 'border-l-4 border-indigo-400 hover:bg-indigo-50/50',
  interested: 'border-l-4 border-green-400 hover:bg-green-50/50',
  reviewed: 'hover:bg-gray-50',
  archived: 'opacity-50 hover:bg-gray-50',
}

const col = createColumnHelper<LeadSummary>()

const columns = [
  col.accessor('lead_score', {
    header: 'Score',
    cell: (info) => {
      const score = info.getValue()
      return (
        <Badge className={`text-xs font-bold border ${scoreBadgeClass(score)}`}>{score}</Badge>
      )
    },
  }),
  col.accessor('opportunity_score', {
    header: 'Opp',
    cell: (info) => {
      const v = info.getValue()
      if (v == null) return <span className="text-gray-300 text-xs">—</span>
      const rounded = Math.round(v)
      const color =
        rounded >= 75
          ? 'text-red-600 font-semibold'
          : rounded >= 50
            ? 'text-amber-600'
            : 'text-gray-500'
      return <span className={`text-xs tabular-nums ${color}`}>{rounded}</span>
    },
  }),
  col.accessor('name', { header: 'Business' }),
  col.accessor('category', {
    header: 'Category',
    cell: (info) => (
      <span className="capitalize text-gray-600 text-sm">{info.getValue() ?? '—'}</span>
    ),
  }),
  col.accessor('website_url', {
    header: 'Website',
    enableSorting: false,
    cell: (info) => {
      const url = info.getValue()
      if (!url)
        return <span className="text-xs text-red-500 font-medium">No website</span>
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="flex items-center gap-1 text-xs text-indigo-600 hover:underline"
        >
          {new URL(url.startsWith('http') ? url : `https://${url}`).hostname}
          <ExternalLink className="h-3 w-3 flex-shrink-0" />
        </a>
      )
    },
  }),
  col.accessor('status', {
    header: 'Status',
    cell: (info) => {
      const s = info.getValue()
      return (
        <Badge className={`text-xs border ${STATUS_CLASS[s] ?? ''}`}>
          {STATUS_LABEL[s] ?? s}
        </Badge>
      )
    },
  }),
  col.accessor('created_at', {
    header: 'Found',
    cell: (info) =>
      new Date(info.getValue()).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      }),
  }),
]

interface LeadTableProps {
  filters: Filters
  onRowClick: (id: number) => void
}

export default function LeadTable({ filters, onRowClick }: LeadTableProps) {
  const [page, setPage] = useState(1)
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'opportunity_score', desc: true },
  ])

  const sortField = sorting[0]
  const statusFilter = filters.showArchived
    ? [...filters.statuses, 'archived']
    : filters.statuses

  const { data, isFetching } = useQuery({
    queryKey: ['leads', filters, page, sorting],
    queryFn: () =>
      fetchLeads({
        search: filters.search || undefined,
        category: filters.categories.length ? filters.categories : undefined,
        status: statusFilter.length ? statusFilter : undefined,
        score_min: filters.scoreMin,
        score_max: filters.scoreMax,
        has_website: filters.hasWebsite,
        sort_by: sortField?.id ?? 'opportunity_score',
        sort_dir: sortField?.desc ? 'desc' : 'asc',
        page,
        page_size: 50,
      }),
    placeholderData: (prev) => prev,
  })

  const table = useReactTable({
    data: data?.leads ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
    manualPagination: true,
  })

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {isFetching && (
        <div className="h-0.5 bg-indigo-400 animate-pulse" />
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left font-semibold select-none"
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ cursor: header.column.getCanSort() ? 'pointer' : 'default' }}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() &&
                        (header.column.getIsSorted() === 'asc' ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : header.column.getIsSorted() === 'desc' ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        ))}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-16 text-gray-400">
                  No leads found. Try adjusting filters or start a scrape.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => {
                const status = row.original.status
                return (
                  <tr
                    key={row.id}
                    onClick={() => onRowClick(row.original.id)}
                    className={`cursor-pointer transition-colors ${ROW_CLASS[status] ?? 'hover:bg-gray-50'}`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
          <span>
            Page {data.page} of {data.pages} — {data.total} leads
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 rounded-md border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="px-3 py-1.5 rounded-md border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
