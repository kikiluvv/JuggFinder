import { fetchScrapeStatus } from '@/api/scrape'
import { fetchStats } from '@/api/leads'
import { useQuery } from '@tanstack/react-query'

export default function StatsBar() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  })

  const { data: scrapeStatus } = useQuery({
    queryKey: ['scrapeStatus'],
    queryFn: fetchScrapeStatus,
    refetchInterval: 3_000,
  })

  const progressPct =
    scrapeStatus?.running && scrapeStatus.categories_total > 0
      ? Math.round((scrapeStatus.categories_done / scrapeStatus.categories_total) * 100)
      : 0

  return (
    <div className="rounded-xl border border-gray-200 bg-white px-6 py-4 shadow-sm">
      <div className="flex items-center gap-6">
        <Stat label="Total Leads" value={stats?.total ?? '—'} />
        <div className="h-8 w-px bg-gray-200" />
        <Stat label="New Today" value={stats?.new_today ?? '—'} accent="indigo" />
        <div className="h-8 w-px bg-gray-200" />
        <Stat
          label="Avg Score"
          value={stats?.avg_score != null ? stats.avg_score.toFixed(1) : '—'}
        />

        {scrapeStatus?.running && (
          <>
            <div className="h-8 w-px bg-gray-200" />
            <div className="flex items-center gap-2 text-sm text-amber-600">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-500" />
              </span>
              <span className="font-medium">
                {scrapeStatus.current_category
                  ? `Scraping ${scrapeStatus.current_category}`
                  : 'Scraping…'}
              </span>
            </div>
          </>
        )}
        {scrapeStatus?.error === 'captcha' && !scrapeStatus.running && (
          <div className="ml-auto flex items-center gap-2 text-sm text-red-600">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
            <span className="font-medium">Last run hit a CAPTCHA — retry later</span>
          </div>
        )}
      </div>

      {scrapeStatus?.running && (
        <div className="mt-3 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>
              Category {scrapeStatus.categories_done} / {scrapeStatus.categories_total} ·{' '}
              {scrapeStatus.businesses_processed} processed ·{' '}
              <span className="text-indigo-600 font-semibold">
                {scrapeStatus.new_leads} new
              </span>
            </span>
            <span className="tabular-nums">{progressPct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full bg-indigo-500 transition-all duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent?: string
}) {
  return (
    <div className="flex flex-col">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
      <span
        className={`text-2xl font-bold tabular-nums ${accent === 'indigo' ? 'text-indigo-600' : 'text-gray-900'}`}
      >
        {value}
      </span>
    </div>
  )
}
