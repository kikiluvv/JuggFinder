import { Button } from '@/components/ui/button'
import { Play } from 'lucide-react'

interface Props {
  onScrapeClick: () => void
}

export default function TopNav({ onScrapeClick }: Props) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white sticky top-0 z-10">
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold tracking-tight text-gray-900">JuggFinder</span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-600 font-semibold">
          Boise
        </span>
      </div>
      <Button onClick={onScrapeClick} size="sm" className="gap-1.5">
        <Play className="h-3.5 w-3.5" />
        Scrape Now
      </Button>
    </header>
  )
}
