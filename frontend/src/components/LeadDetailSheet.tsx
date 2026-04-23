import { draftOutreach, fetchLead, rescanLead, updateLead } from '@/api/leads'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  Check,
  Clock,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Sparkles,
  Star,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { LeadDetail, LeadStatus } from '@/types'

const STATUS_OPTIONS: { value: LeadStatus; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'interested', label: 'Interested' },
  { value: 'archived', label: 'Archived' },
]

const SCORE_CLASS: Record<string, string> = {
  high: 'bg-red-100 text-red-700 border-red-200 text-lg font-bold',
  mid: 'bg-amber-100 text-amber-700 border-amber-200 text-lg font-bold',
  low: 'bg-gray-100 text-gray-600 border-gray-200 text-lg font-bold',
}

function scoreClass(score: number) {
  if (score >= 8) return SCORE_CLASS.high
  if (score >= 5) return SCORE_CLASS.mid
  return SCORE_CLASS.low
}

interface Props {
  leadId: number | null
  onClose: () => void
}

export default function LeadDetailSheet({ leadId, onClose }: Props) {
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState('')
  const [draft, setDraft] = useState('')
  const [savedIndicator, setSavedIndicator] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const draftDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: lead, isLoading } = useQuery({
    queryKey: ['lead', leadId],
    queryFn: () => fetchLead(leadId!),
    enabled: !!leadId,
  })

  useEffect(() => {
    if (lead) {
      setNotes(lead.notes ?? '')
      setDraft(lead.outreach_draft ?? '')
    }
  }, [lead])

  const mutation = useMutation({
    mutationFn: ({ data }: { data: { status?: string; notes?: string; outreach_draft?: string } }) =>
      updateLead(lead!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['lead', leadId] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      setSavedIndicator(true)
      setTimeout(() => setSavedIndicator(false), 2000)
    },
  })

  const rescanMutation = useMutation({
    mutationFn: () => rescanLead(lead!.id),
    onSuccess: (fresh: LeadDetail) => {
      queryClient.setQueryData(['lead', leadId], fresh)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const draftMutation = useMutation({
    mutationFn: () => draftOutreach(lead!.id),
    onSuccess: ({ draft: text }) => {
      setDraft(text)
      queryClient.invalidateQueries({ queryKey: ['lead', leadId] })
    },
  })

  function handleStatusChange(status: string | null) {
    if (status) mutation.mutate({ data: { status } })
  }

  function handleNotesChange(value: string) {
    setNotes(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      mutation.mutate({ data: { notes: value } })
    }, 1000)
  }

  function handleDraftChange(value: string) {
    setDraft(value)
    if (draftDebounceRef.current) clearTimeout(draftDebounceRef.current)
    draftDebounceRef.current = setTimeout(() => {
      mutation.mutate({ data: { outreach_draft: value } })
    }, 1000)
  }

  function handleArchive() {
    mutation.mutate({ data: { status: 'archived' } })
    onClose()
  }

  function copyToClipboard(label: string, value: string) {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(label)
      setTimeout(() => setCopied(null), 1500)
    })
  }

  return (
    <Sheet open={!!leadId} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        {isLoading || !lead ? (
          <div className="flex items-center justify-center h-full text-gray-400">Loading…</div>
        ) : (
          <div className="flex flex-col gap-5 pb-6">
            <SheetHeader>
              <SheetTitle className="text-xl">{lead.name}</SheetTitle>
              <div className="flex items-center gap-3 flex-wrap text-sm text-gray-500">
                {lead.category && (
                  <span className="capitalize bg-gray-100 px-2 py-0.5 rounded text-xs">
                    {lead.category}
                  </span>
                )}
                {lead.rating != null && (
                  <span className="flex items-center gap-0.5">
                    <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
                    {lead.rating.toFixed(1)}
                    {lead.review_count != null && (
                      <span className="text-gray-400 ml-0.5">({lead.review_count})</span>
                    )}
                  </span>
                )}
                <Badge className={`border ${scoreClass(lead.lead_score)}`}>
                  Score {lead.lead_score}
                </Badge>
                {lead.opportunity_score != null && (
                  <span className="text-xs text-gray-400">
                    Opp {lead.opportunity_score.toFixed(0)}
                  </span>
                )}
                {lead.is_claimed === false && (
                  <Badge className="border bg-purple-50 text-purple-700 border-purple-200 text-[10px]">
                    Unclaimed
                  </Badge>
                )}
              </div>
            </SheetHeader>

            <Separator />

            {/* Contact info */}
            <div className="space-y-2">
              {lead.address && (
                <div className="flex items-start justify-between gap-2">
                  <a
                    href={`https://maps.google.com/?q=${encodeURIComponent(lead.address)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 text-sm text-indigo-600 hover:underline"
                  >
                    <MapPin className="h-4 w-4 mt-0.5 flex-shrink-0" />
                    {lead.address}
                  </a>
                  <CopyButton
                    label={`addr-${lead.id}`}
                    copied={copied}
                    onClick={() => copyToClipboard(`addr-${lead.id}`, lead.address!)}
                  />
                </div>
              )}
              {lead.phone && (
                <div className="flex items-center justify-between gap-2">
                  <a
                    href={`tel:${lead.phone}`}
                    className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
                  >
                    <Phone className="h-4 w-4 flex-shrink-0" />
                    {lead.phone}
                  </a>
                  <CopyButton
                    label={`phone-${lead.id}`}
                    copied={copied}
                    onClick={() => copyToClipboard(`phone-${lead.id}`, lead.phone!)}
                  />
                </div>
              )}
              {lead.email && (
                <div className="flex items-center justify-between gap-2">
                  <a
                    href={`mailto:${lead.email}`}
                    className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
                  >
                    <Mail className="h-4 w-4 flex-shrink-0" />
                    {lead.email}
                  </a>
                  <CopyButton
                    label={`email-${lead.id}`}
                    copied={copied}
                    onClick={() => copyToClipboard(`email-${lead.id}`, lead.email!)}
                  />
                </div>
              )}
              {lead.website_url ? (
                <a
                  href={lead.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-indigo-600 hover:underline break-all"
                >
                  <ExternalLink className="h-4 w-4 flex-shrink-0" />
                  {lead.website_url}
                </a>
              ) : (
                <p className="text-sm text-red-500 font-medium">No website detected</p>
              )}
              {lead.hours && (
                <div className="flex items-start gap-2 text-sm text-gray-600">
                  <Clock className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  {lead.hours}
                </div>
              )}
              {lead.photo_count != null && (
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <ImageIcon className="h-3.5 w-3.5" />
                  {lead.photo_count} photo{lead.photo_count === 1 ? '' : 's'} on listing
                </div>
              )}
              {lead.google_categories.length > 0 && (
                <div className="flex items-start gap-2 text-xs text-gray-500">
                  <Building2 className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                  <span className="flex flex-wrap gap-1">
                    {lead.google_categories.map((c) => (
                      <span key={c} className="bg-gray-100 rounded px-1.5 py-0.5">
                        {c}
                      </span>
                    ))}
                  </span>
                </div>
              )}
            </div>

            {lead.business_description && (
              <>
                <Separator />
                <p className="text-sm text-gray-600">{lead.business_description}</p>
              </>
            )}

            <Separator />

            {/* Web signals */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Signal label="HTTPS" value={lead.has_ssl} />
              <Signal label="Mobile Friendly" value={lead.has_mobile_viewport} />
              <Signal label="HTTP Status" value={lead.website_status_code} raw />
              <Signal label="Copyright Year" value={lead.copyright_year} raw />
              <Signal label="AI Score" value={lead.ai_score} raw />
              <Signal label="Opportunity" value={lead.opportunity_score?.toFixed(0)} raw />
            </div>

            {lead.tech_stack.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Tech Stack
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {lead.tech_stack.map((t) => (
                    <span
                      key={t}
                      className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded capitalize"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* AI issues */}
            {lead.ai_issues?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  Detected Issues
                </p>
                <ul className="space-y-1">
                  {lead.ai_issues.map((issue, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-red-400 flex-shrink-0" />
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* AI summary */}
            {lead.ai_summary && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                  AI Summary
                </p>
                <p className="text-sm italic text-gray-600">{lead.ai_summary}</p>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 flex-1"
                onClick={() => rescanMutation.mutate()}
                disabled={rescanMutation.isPending}
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${rescanMutation.isPending ? 'animate-spin' : ''}`}
                />
                {rescanMutation.isPending ? 'Rescanning…' : 'Rescan site'}
              </Button>
              <Button
                size="sm"
                className="gap-1.5 flex-1"
                onClick={() => draftMutation.mutate()}
                disabled={draftMutation.isPending}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {draftMutation.isPending
                  ? 'Drafting…'
                  : draft
                    ? 'Regenerate draft'
                    : 'AI draft outreach'}
              </Button>
            </div>

            <Separator />

            {/* Outreach draft */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Outreach Draft
                </p>
                {draft && (
                  <button
                    onClick={() => copyToClipboard(`draft-${lead.id}`, draft)}
                    className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
                  >
                    {copied === `draft-${lead.id}` ? (
                      <>
                        <Check className="h-3 w-3" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" /> Copy
                      </>
                    )}
                  </button>
                )}
              </div>
              <Textarea
                value={draft}
                onChange={(e) => handleDraftChange(e.target.value)}
                placeholder="Click 'AI draft outreach' to generate a first message…"
                className="resize-none text-sm"
                rows={5}
              />
              {draftMutation.isError && (
                <p className="text-xs text-red-500 mt-1">
                  {(draftMutation.error as Error).message}
                </p>
              )}
            </div>

            {/* Status */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                Status
              </p>
              <Select value={lead.status} onValueChange={handleStatusChange}>
                <SelectTrigger className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map(({ value, label }) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Notes */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Notes
                </p>
                {savedIndicator && (
                  <span className="text-xs text-green-600 font-medium">Saved ✓</span>
                )}
              </div>
              <Textarea
                value={notes}
                onChange={(e) => handleNotesChange(e.target.value)}
                placeholder="Add notes about this lead…"
                className="resize-none text-sm"
                rows={4}
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-400">
                Found{' '}
                {new Date(lead.created_at).toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
                {lead.last_scanned_at && (
                  <>
                    {' '}
                    · Scanned{' '}
                    {new Date(lead.last_scanned_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    })}
                  </>
                )}
              </p>
              <button
                onClick={handleArchive}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Archive
              </button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function CopyButton({
  label,
  copied,
  onClick,
}: {
  label: string
  copied: string | null
  onClick: () => void
}) {
  const active = copied === label
  return (
    <button
      onClick={onClick}
      className="text-gray-400 hover:text-indigo-600 transition-colors flex-shrink-0"
      title={active ? 'Copied!' : 'Copy to clipboard'}
    >
      {active ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

function Signal({
  label,
  value,
  raw,
}: {
  label: string
  value: boolean | number | string | null | undefined
  raw?: boolean
}) {
  let display: string
  let cls = 'text-gray-600'

  if (value === null || value === undefined) {
    display = '—'
    cls = 'text-gray-400'
  } else if (raw) {
    display = String(value)
  } else {
    display = value ? '✓ Yes' : '✗ No'
    cls = value ? 'text-green-600' : 'text-red-500'
  }

  return (
    <div className="rounded-lg bg-gray-50 p-2.5">
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className={`text-sm font-medium ${cls}`}>{display}</p>
    </div>
  )
}
