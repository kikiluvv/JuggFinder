import { startScrape } from '@/api/scrape'
import { fetchCategories, fetchScrapeStatus } from '@/api/scrape'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

interface Props {
  open: boolean
  onClose: () => void
}

export default function ScrapeModal({ open, onClose }: Props) {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string[]>([])
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const { data: catData } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    staleTime: Infinity,
  })
  const categories = catData?.categories ?? []

  const { data: scrapeStatus } = useQuery({
    queryKey: ['scrapeStatus'],
    queryFn: fetchScrapeStatus,
    refetchInterval: 5_000,
  })

  const isRunning = scrapeStatus?.running ?? false
  const allSelected = selected.length === categories.length && categories.length > 0

  function toggleAll(checked: boolean) {
    setSelected(checked ? [...categories] : [])
  }

  function toggleOne(cat: string, checked: boolean) {
    setSelected((prev) => (checked ? [...prev, cat] : prev.filter((c) => c !== cat)))
  }

  const mutation = useMutation({
    mutationFn: () =>
      startScrape(allSelected ? ['all'] : selected),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scrapeStatus'] })
      setErrorMsg(null)
      onClose()
    },
    onError: (err: Error) => {
      setErrorMsg(err.message)
    },
  })

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Scrape Now</DialogTitle>
          <p className="text-sm text-gray-500 mt-1">
            Select categories to scrape from Google Maps.
          </p>
        </DialogHeader>

        <div className="mt-2 space-y-3 max-h-72 overflow-y-auto pr-1">
          {/* Select all */}
          <div className="flex items-center gap-2 pb-2 border-b border-gray-100">
            <Checkbox
              id="select-all"
              checked={allSelected}
              onCheckedChange={(c) => toggleAll(!!c)}
            />
            <label htmlFor="select-all" className="text-sm font-semibold cursor-pointer">
              Select All ({categories.length})
            </label>
          </div>

          {categories.map((cat) => (
            <div key={cat} className="flex items-center gap-2">
              <Checkbox
                id={`modal-cat-${cat}`}
                checked={selected.includes(cat)}
                onCheckedChange={(c) => toggleOne(cat, !!c)}
              />
              <label htmlFor={`modal-cat-${cat}`} className="text-sm capitalize cursor-pointer">
                {cat}
              </label>
            </div>
          ))}
        </div>

        {errorMsg && (
          <p className="text-sm text-red-500 mt-2">{errorMsg}</p>
        )}

        {isRunning && (
          <p className="text-sm text-amber-600 font-medium mt-2">
            ⚠ A scrape is already in progress.
          </p>
        )}

        <DialogFooter className="mt-4 gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={selected.length === 0 || isRunning || mutation.isPending}
          >
            {mutation.isPending ? 'Starting…' : 'Start Scrape'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
