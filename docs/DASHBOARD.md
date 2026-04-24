# Dashboard UI Specification

The JuggFinder dashboard is a local React app (Vite + Tailwind + shadcn/ui) served at `localhost:5173`. It is the primary interface for reviewing, managing, and triggering scrape jobs. It is not hosted externally.

## Layout Overview

```
┌──────────────────────────────────────────────────────────────┐
│  JuggFinder                          [Scrape Now]  [⚙ Settings] │
├──────────────────────────────────────────────────────────────┤
│  Stats Bar                                                    │
│  Total: 247 | New: 12 | Avg Score: 7.2 | [● Scraping...]    │
├──────────────────────────────────────────────────────────────┤
│  Filters & Search                                            │
│  [Search by name or address...]  [Category ▼] [Status ▼]    │
│  [Score: 1 ──────●── 10]  [Has Website: All ▼]  [Clear]     │
├──────────────────────────────────────────────────────────────┤
│  Lead Table (sortable)                                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ # │ Business Name  │ Category │ Score │ Website │ Status│  │
│  │ ─ │ ─────────────  │ ──────── │ ───── │ ─────── │ ─────│  │
│  │ 1 │ Tito's Auto... │ Auto Rep │  10   │ None    │ New  │  │
│  │ 2 │ Bloom Salon    │ Salon    │   9   │ FB only │ New  │  │
│  │   │ ...            │          │       │         │      │  │
│  └────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│  Lead Detail Panel (right side drawer, opens on row click)   │
│  Business Name, Address, Phone, Category                     │
│  Website URL (clickable link or "None")                      │
│  Score Badge + Issues List + AI Summary                      │
│  Status Dropdown  |  Notes Textarea  |  [Save]  [Archive]   │
└──────────────────────────────────────────────────────────────┘
```

---

## Color Coding by Status

Visual distinction is critical so new leads immediately stand out from processed ones.

| Status | Visual Treatment |
|---|---|
| `new` | Highlighted row — blue-indigo left border + subtle blue background tint |
| `reviewed` | Normal row — no highlight, default background |
| `interested` | Green left border + subtle green background tint |
| `archived` | Muted — lower opacity, grey text, hidden by default (toggle to show) |

New leads should visually "pop" relative to everything else. Use Tailwind classes like `border-l-4 border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30` for the new state.

---

## Stats Bar
Always visible at the top. Updates in real time (polling `/leads/stats` every 30s or on scrape completion).

| Stat | Source |
|---|---|
| Total Leads | Count of all non-archived leads |
| New Today | Leads with `created_at` = today and `status = new` |
| Avg Score | Mean lead score across all active leads |
| Scraping Indicator | Polls `GET /scrape/status`; shows animated dot + "Scraping..." when active |

---

## Lead Table

### Columns
| Column | Sortable | Notes |
|---|---|---|
| Score | Yes (default desc) | Displayed as a colored badge (red=low, yellow=mid, green=high) |
| Business Name | Yes | Truncated to ~30 chars, full name in detail panel |
| Category | Yes | e.g., "Restaurant", "Plumber" |
| Website | No | "None" (red badge), "Social only" (orange badge), or truncated URL |
| Status | Yes | Pill badge: New / Reviewed / Interested |
| Date Found | Yes | Relative time (e.g., "2 days ago") |

### Sorting
- Click any column header to sort ascending; click again for descending.
- Default sort: Score descending (highest priority leads first).

### Pagination
- 50 leads per page, with page controls at the bottom.
- Or infinite scroll — decide during implementation.

---

## Filters & Search

### Search
- Single text input — filters by business name OR address (case-insensitive, debounced 300ms).

### Category Filter
- Multi-select dropdown — shows all configured categories.
- Default: All selected.

### Status Filter
- Multi-select pills or dropdown.
- Default: `new`, `reviewed`, `interested` shown. `archived` hidden by default.
- "Show Archived" toggle to include archived leads.

### Score Range Filter
- Dual-handle range slider: min 1, max 10.
- Default: 5–10 (only medium-to-high priority leads shown by default).

### Website Filter
- Dropdown: All / No Website / Has Website / Social Only.

### Clear Filters Button
- Resets all filters and search to defaults.

---

## Lead Detail Panel (Side Drawer)

Opens when a table row is clicked. Slides in from the right. Does not navigate away.

### Contents
- **Business Name** (large heading)
- **Category** | **Rating** (star count) | **Review Count**
- **Address** (with Google Maps link)
- **Phone Number** (clickable `tel:` link)
- **Website URL** — clickable external link, or "No website detected" in red
- **Lead Score** — large badge with color (matches table badge)
- **Detected Issues** — bulleted list from AI (e.g., "No HTTPS", "No mobile viewport", "Copyright 2014 found")
- **AI Summary** — one-sentence Gemini/Groq summary of website quality
- **Date Found** — full timestamp
- **Status** — dropdown to change status (changes saved immediately via PATCH)
- **Notes** — free-form textarea; saved via debounced auto-save or explicit "Save Notes" button
- **Archive Button** — moves lead to `archived` status and closes the panel

---

## "Scrape Now" Modal

Triggered by the "Scrape Now" button in the top nav. Opens a modal dialog.

### Contents
- **Title:** "Start a Scrape Job"
- **Category Selection:**
  - "Select All" checkbox at top (checks/unchecks all)
  - Individual checkboxes for each category (from `GET /categories`)
- **Estimated time note:** "Scraping all categories typically takes 15–30 minutes."
- **Buttons:** [Cancel] [Start Scrape]

### Behavior After Clicking "Start Scrape"
- Modal closes.
- Stats bar shows animated "Scraping..." indicator.
- Dashboard polls `/scrape/status` every 5 seconds.
- When scrape finishes, lead table refreshes automatically and indicator disappears.

---

## Settings Panel (Optional, Future)

Accessible via a gear icon in the top nav. Could contain:
- `SCRAPE_SCHEDULE_TIME` — change the daily scrape time
- Category list management (add/remove)
- Clear all leads / reset database

---

## Technology Notes for Implementation

- Use **shadcn/ui** components: `Table`, `Sheet` (side drawer), `Dialog` (modal), `Badge`, `Slider`, `Select`, `Checkbox`, `Textarea`, `Button`.
- Use **TanStack Query** (`@tanstack/react-query`) for data fetching, caching, and auto-refetch on scrape completion.
- Use **TanStack Table** (`@tanstack/react-table`) for sortable, filterable table logic.
- The dashboard should be dark-mode capable (Tailwind `dark:` variants), but light mode is the default.
- No authentication required — this is a local-only app.
