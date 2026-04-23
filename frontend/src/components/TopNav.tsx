import { Button } from '@/components/ui/button'
import { toggleTheme } from '@/lib/theme'
import { Moon, Play, Settings, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

interface Props {
  onScrapeClick: () => void
  onSettingsClick: () => void
}

export default function TopNav({ onScrapeClick, onSettingsClick }: Props) {
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'))
  }, [])

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card sticky top-0 z-10">
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold tracking-tight text-foreground">JuggFinder</span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-600 font-semibold">
          Boise
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const next = toggleTheme()
            setIsDark(next === 'dark')
          }}
          className="gap-1.5"
          title={isDark ? 'Switch to light' : 'Switch to dark'}
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          Theme
        </Button>
        <Button variant="outline" size="sm" onClick={onSettingsClick} className="gap-1.5">
          <Settings className="h-3.5 w-3.5" />
          Settings
        </Button>
        <Button onClick={onScrapeClick} size="sm" className="gap-1.5">
          <Play className="h-3.5 w-3.5" />
          Scrape Now
        </Button>
      </div>
    </header>
  )
}
