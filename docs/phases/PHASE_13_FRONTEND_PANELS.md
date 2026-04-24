# Phase 13 — Frontend Panels & Modals

## Goal
Build the lead detail side drawer and the "Scrape Now" modal. After this phase the UI is feature-complete.

## Completion Criteria
- [ ] Clicking any table row opens the lead detail `Sheet` without navigating away
- [ ] Sheet shows all fields defined in `DASHBOARD.md` (name, address, phone, website, score, issues, AI summary, status, notes)
- [ ] Status dropdown change is saved immediately via `PATCH /leads/{id}`
- [ ] Notes textarea auto-saves after 1s of no input (debounced), OR has an explicit "Save Notes" button
- [ ] "Archive" button sets status to `archived` and closes the drawer
- [ ] "Scrape Now" button in nav opens the category selection `Dialog`
- [ ] Dialog shows "Select All" checkbox + individual category checkboxes (from `GET /categories`)
- [ ] Clicking "Start Scrape" sends `POST /scrape/start` and closes the modal
- [ ] If a scrape is already running, the "Start Scrape" button is disabled with a tooltip
- [ ] After scrape starts, the lead table automatically refetches when `running` transitions to `false`

---

## Lead Detail Sheet (`LeadDetailSheet.tsx`)

```typescript
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
```

Opens via a `selectedLeadId: number | null` state in `Dashboard.tsx`. Pass it down and set it on row click.

Fetch the detail data:
```typescript
const { data: lead } = useQuery({
  queryKey: ['lead', selectedLeadId],
  queryFn: () => fetchLead(selectedLeadId!),
  enabled: !!selectedLeadId,
})
```

### Status Change

```typescript
const updateMutation = useMutation({
  mutationFn: ({ id, data }) => updateLead(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['leads'] })
    queryClient.invalidateQueries({ queryKey: ['lead', lead.id] })
    queryClient.invalidateQueries({ queryKey: ['stats'] })
  },
})
```

### Notes Auto-Save

Use `useDebounce` (or a `setTimeout` ref) to trigger the `PATCH` after 1 second of inactivity. Show a subtle "Saved" indicator briefly after success.

### Fields to Display

- Business Name (large heading)
- Category | Rating (⭐ n.n) | Review Count
- Address — with Google Maps deep link: `https://maps.google.com/?q={encodeURIComponent(address)}`
- Phone — `<a href="tel:{phone}">` clickable
- Website URL — external link (target `_blank`), or red "No website detected" text
- Lead Score — large colored badge
- Detected Issues — bulleted list (`ai_issues` array)
- AI Summary — italicized one-sentence description
- Date Found — full formatted timestamp
- Status — shadcn `Select` dropdown
- Notes — shadcn `Textarea`
- Archive Button — `variant="outline"` at the bottom; sets status to `archived` and closes sheet

---

## Scrape Now Modal (`ScrapeModal.tsx`)

```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
```

Trigger from `TopNav.tsx` via a `isScrapeModalOpen` state lifted to `Dashboard.tsx`.

### Category Checkboxes

Fetch from `GET /categories`:
```typescript
const { data } = useQuery({ queryKey: ['categories'], queryFn: fetchCategories })
```

State: `selectedCategories: string[]`. "Select All" checkbox is checked when `selectedCategories.length === categories.length`.

### Start Scrape Action

```typescript
const startMutation = useMutation({
  mutationFn: () => startScrape(selectedCategories.length === categories.length ? ['all'] : selectedCategories),
  onSuccess: () => {
    setIsScrapeModalOpen(false)
    queryClient.invalidateQueries({ queryKey: ['scrapeStatus'] })
  },
  onError: () => {
    // Show toast/error: "A scrape is already in progress"
  }
})
```

### Auto-Refresh After Scrape Completes

In `Dashboard.tsx`, watch the `scrapeStatus` query. When `running` transitions from `true` → `false`, invalidate the leads and stats queries:
```typescript
const prevRunning = useRef(false)
useEffect(() => {
  if (prevRunning.current && !scrapeStatus?.running) {
    queryClient.invalidateQueries({ queryKey: ['leads'] })
    queryClient.invalidateQueries({ queryKey: ['stats'] })
  }
  prevRunning.current = scrapeStatus?.running ?? false
}, [scrapeStatus?.running])
```

---

## Done When
The full user workflow works end-to-end: open dashboard → view leads → click row → review details → change status → start scrape from modal → see scraping indicator → leads refresh automatically when done.
