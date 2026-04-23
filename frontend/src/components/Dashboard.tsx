import { fetchScrapeStatus } from '@/api/scrape'
import FilterBar from '@/components/FilterBar'
import LeadDetailSheet from '@/components/LeadDetailSheet'
import LeadTable from '@/components/LeadTable'
import ScrapeModal from '@/components/ScrapeModal'
import SettingsDialog from '@/components/SettingsDialog'
import StatsBar from '@/components/StatsBar'
import TopNav from '@/components/TopNav'
import { useFilters } from '@/hooks/useFilters'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const { filters, onChange, onReset } = useFilters()
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null)
  const [scrapeModalOpen, setScrapeModalOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const prevRunning = useRef(false)

  const { data: scrapeStatus } = useQuery({
    queryKey: ['scrapeStatus'],
    queryFn: fetchScrapeStatus,
    refetchInterval: 5_000,
  })

  // Auto-refresh leads when a scrape transitions from running → done
  useEffect(() => {
    if (prevRunning.current && !scrapeStatus?.running) {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    }
    prevRunning.current = scrapeStatus?.running ?? false
  }, [scrapeStatus?.running, queryClient])

  return (
    <div className="min-h-screen bg-background">
      <TopNav
        onScrapeClick={() => setScrapeModalOpen(true)}
        onSettingsClick={() => setSettingsOpen(true)}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <StatsBar />

        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5 items-start">
          <FilterBar filters={filters} onChange={onChange} onReset={onReset} />
          <LeadTable filters={filters} onRowClick={setSelectedLeadId} />
        </div>
      </main>

      <LeadDetailSheet leadId={selectedLeadId} onClose={() => setSelectedLeadId(null)} />

      <ScrapeModal open={scrapeModalOpen} onClose={() => setScrapeModalOpen(false)} />
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
