# Phase 11 — Frontend Setup

## Goal
Get the Vite + React + TypeScript + Tailwind + shadcn/ui frontend wired up with TanStack Query and a working API client layer so every subsequent phase can build components without setup friction.

## Completion Criteria
- [ ] `npm run dev` boots at `localhost:5173` without errors
- [ ] Tailwind CSS is working (a test class applies correctly in the browser)
- [ ] shadcn/ui is initialized; at least one component (`Button`) renders
- [ ] TanStack Query `QueryClientProvider` wraps the app in `main.tsx`
- [ ] `src/api/` contains typed fetch functions for every backend endpoint
- [ ] `src/types.ts` defines all shared TypeScript interfaces
- [ ] Vite proxy configured so `/api/*` → `localhost:8000` (avoids CORS in dev)

---

## Vite Proxy (`vite.config.ts`)

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

---

## `src/types.ts`

```typescript
export type LeadStatus = 'new' | 'reviewed' | 'interested' | 'archived'

export interface LeadSummary {
  id: number
  name: string
  category: string | null
  lead_score: number
  website_url: string | null
  status: LeadStatus
  created_at: string
}

export interface LeadDetail extends LeadSummary {
  address: string | null
  phone: string | null
  rating: number | null
  review_count: number | null
  has_ssl: boolean | null
  has_mobile_viewport: boolean | null
  website_status_code: number | null
  copyright_year: number | null
  ai_score: number | null
  ai_issues: string[]
  ai_summary: string | null
  notes: string | null
  updated_at: string
}

export interface LeadsResponse {
  leads: LeadSummary[]
  total: number
  page: number
  pages: number
}

export interface StatsResponse {
  total: number
  new_today: number
  avg_score: number
}

export interface ScrapeStatus {
  running: boolean
  started_at: string | null
  categories: string[]
}
```

---

## `src/api/` — Typed API Layer

Create individual files per resource domain:

**`src/api/leads.ts`** — functions: `fetchLeads(params)`, `fetchLead(id)`, `updateLead(id, data)`, `deleteLead(id)`, `fetchStats()`

**`src/api/scrape.ts`** — functions: `startScrape(categories)`, `fetchScrapeStatus()`, `fetchCategories()`

Each function uses `fetch('/api/...')` and returns typed responses. Throw on non-ok status.

---

## `src/main.tsx` — QueryClient Setup

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
)
```

---

## shadcn/ui Component Installation (as needed per phase)

Install components as they're needed in subsequent phases. Don't install all at once. Commands follow the pattern:
```bash
npx shadcn@latest add button
npx shadcn@latest add table sheet dialog badge slider select checkbox textarea
```

---

## Done When
The app renders a placeholder page with a shadcn `Button` that is styled correctly. `useQuery({ queryKey: ['stats'], queryFn: fetchStats })` in a test component returns data from the backend without CORS errors.
