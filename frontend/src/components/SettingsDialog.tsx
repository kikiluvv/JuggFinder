import {
  addSuppression,
  deleteSuppression,
  fetchOutreachPolicy,
  fetchOutreachUsageToday,
  fetchSettings,
  fetchSuppressions,
  updateOutreachPolicy,
  updateSettings,
  type OutreachPolicyResponse,
  type SettingsResponse,
} from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

interface Props {
  open: boolean
  onClose: () => void
}

const GEMINI_MODELS: { id: string; label: string }[] = [
  { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (recommended)' },
  { id: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash-Lite (cheapest)' },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (strongest)' },
  { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (legacy)' },
  { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (legacy)' },
  { id: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (legacy)' },
]

const GROQ_MODELS: { id: string; label: string }[] = [
  { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B Versatile' },
  { id: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B Instant (fast/cheap)' },
  { id: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B 32K' },
  { id: 'gemma2-9b-it', label: 'Gemma 2 9B IT' },
]

const CUSTOM = '__custom__'

function buildPatch(original: SettingsResponse, form: SettingsResponse, secrets: {
  gemini_api_key: string
  groq_api_key: string
  smtp_password: string
}) {
  const patch: Record<string, unknown> = {}

  if (secrets.gemini_api_key.trim()) patch.gemini_api_key = secrets.gemini_api_key.trim()
  if (secrets.groq_api_key.trim()) patch.groq_api_key = secrets.groq_api_key.trim()
  if (secrets.smtp_password.trim()) patch.smtp_password = secrets.smtp_password.trim()

  ;(
    [
      'gemini_model',
      'groq_model',
      'scrape_schedule_time',
      'scrape_location',
      'scrape_max_results',
      'scrape_headless',
      'scrape_user_agent',
      'outreach_send_enabled',
      'outreach_sender_name',
      'outreach_sender_email',
      'smtp_host',
      'smtp_port',
      'smtp_username',
      'smtp_use_tls',
    ] as const
  ).forEach((k) => {
    if (form[k] !== original[k]) patch[k] = form[k]
  })

  return patch
}

export default function SettingsDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    enabled: open,
  })
  const { data: policy } = useQuery({
    queryKey: ['outreachPolicy'],
    queryFn: fetchOutreachPolicy,
    enabled: open,
  })
  const { data: usage } = useQuery({
    queryKey: ['outreachUsageToday'],
    queryFn: fetchOutreachUsageToday,
    enabled: open,
  })
  const { data: suppressions } = useQuery({
    queryKey: ['outreachSuppressions'],
    queryFn: () => fetchSuppressions(),
    enabled: open,
  })

  const [form, setForm] = useState<SettingsResponse | null>(null)
  const [policyForm, setPolicyForm] = useState<OutreachPolicyResponse | null>(null)
  const [geminiKey, setGeminiKey] = useState('')
  const [groqKey, setGroqKey] = useState('')
  const [smtpPassword, setSmtpPassword] = useState('')
  const [suppressionEmail, setSuppressionEmail] = useState('')
  const [suppressionReason, setSuppressionReason] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [policyError, setPolicyError] = useState<string | null>(null)
  const [geminiModelMode, setGeminiModelMode] = useState<string>('gemini-2.5-flash')
  const [geminiCustomModel, setGeminiCustomModel] = useState('')
  const [groqModelMode, setGroqModelMode] = useState<string>('llama-3.3-70b-versatile')
  const [groqCustomModel, setGroqCustomModel] = useState('')

  useEffect(() => {
    if (data) {
      setForm(data)
      setGeminiKey('')
      setGroqKey('')
      setSmtpPassword('')
      setErrorMsg(null)

      const geminiKnown = GEMINI_MODELS.some((m) => m.id === data.gemini_model)
      setGeminiModelMode(geminiKnown ? data.gemini_model : CUSTOM)
      setGeminiCustomModel(geminiKnown ? '' : data.gemini_model)

      const groqKnown = GROQ_MODELS.some((m) => m.id === data.groq_model)
      setGroqModelMode(groqKnown ? data.groq_model : CUSTOM)
      setGroqCustomModel(groqKnown ? '' : data.groq_model)
    }
  }, [data])

  useEffect(() => {
    if (policy) {
      setPolicyForm(policy)
      setPolicyError(null)
    }
  }, [policy])

  const original = data
  const canSave = useMemo(() => {
    if (!original || !form) return false
    const patch = buildPatch(original, form, {
      gemini_api_key: geminiKey,
      groq_api_key: groqKey,
      smtp_password: smtpPassword,
    })
    return Object.keys(patch).length > 0
  }, [original, form, geminiKey, groqKey, smtpPassword])

  const mutation = useMutation({
    mutationFn: async () => {
      if (!original || !form) return null
      const patch = buildPatch(original, form, {
        gemini_api_key: geminiKey,
        groq_api_key: groqKey,
        smtp_password: smtpPassword,
      })
      return updateSettings(patch)
    },
    onSuccess: (fresh) => {
      if (fresh) {
        queryClient.setQueryData(['settings'], fresh)
        setForm(fresh)
        setGeminiKey('')
        setGroqKey('')
        setSmtpPassword('')
      }
      setErrorMsg(null)
    },
    onError: (err: Error) => setErrorMsg(err.message),
  })

  const policyMutation = useMutation({
    mutationFn: async () => {
      if (!policy || !policyForm) return null
      const patch: Record<string, unknown> = {}
      ;(
        [
          'outreach_enabled',
          'outreach_daily_send_cap',
          'outreach_send_window_start',
          'outreach_send_window_end',
          'outreach_send_timezone',
          'outreach_enforce_window',
          'outreach_enforce_daily_cap',
          'outreach_enforce_suppression',
        ] as const
      ).forEach((k) => {
        if (policyForm[k] !== policy[k]) patch[k] = policyForm[k]
      })
      if (
        policyForm.outreach_allowed_statuses.join(',') !== policy.outreach_allowed_statuses.join(',')
      ) {
        patch.outreach_allowed_statuses = policyForm.outreach_allowed_statuses
      }
      if (Object.keys(patch).length === 0) return null
      return updateOutreachPolicy(patch)
    },
    onSuccess: (fresh) => {
      if (fresh) {
        queryClient.setQueryData(['outreachPolicy'], fresh)
        setPolicyForm(fresh)
      }
      queryClient.invalidateQueries({ queryKey: ['outreachUsageToday'] })
      setPolicyError(null)
    },
    onError: (err: Error) => setPolicyError(err.message),
  })

  const addSuppressionMutation = useMutation({
    mutationFn: () =>
      addSuppression({
        email: suppressionEmail,
        reason: suppressionReason || undefined,
      }),
    onSuccess: () => {
      setSuppressionEmail('')
      setSuppressionReason('')
      queryClient.invalidateQueries({ queryKey: ['outreachSuppressions'] })
    },
    onError: (err: Error) => setPolicyError(err.message),
  })

  const removeSuppressionMutation = useMutation({
    mutationFn: (id: number) => deleteSuppression(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['outreachSuppressions'] })
    },
    onError: (err: Error) => setPolicyError(err.message),
  })

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            SMTP/app settings are saved to <code className="text-xs">.env</code>. Guardrail policy and
            suppressions are stored in your local database.
          </p>
        </DialogHeader>

        {isLoading || !form ? (
          <div className="py-10 text-center text-muted-foreground">Loading…</div>
        ) : (
          <div className="mt-2 space-y-5">
            <section className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">AI</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Gemini API key</Label>
                  <input
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    placeholder={form.gemini_api_key_set ? 'Key is set (leave blank to keep)' : 'Paste key…'}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    type="password"
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Groq API key</Label>
                  <input
                    value={groqKey}
                    onChange={(e) => setGroqKey(e.target.value)}
                    placeholder={form.groq_api_key_set ? 'Key is set (leave blank to keep)' : 'Paste key…'}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    type="password"
                    autoComplete="off"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Gemini model</Label>
                  <Select
                    value={geminiModelMode}
                    onValueChange={(v) => {
                      if (!v) return
                      setGeminiModelMode(v)
                      const next = v === CUSTOM ? (geminiCustomModel || form.gemini_model) : v
                      setForm((p) => (p ? { ...p, gemini_model: next } : p))
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent align="start">
                      {GEMINI_MODELS.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.label}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM}>Custom model…</SelectItem>
                    </SelectContent>
                  </Select>
                  {geminiModelMode === CUSTOM && (
                    <input
                      value={geminiCustomModel}
                      onChange={(e) => {
                        setGeminiCustomModel(e.target.value)
                        setForm((p) => (p ? { ...p, gemini_model: e.target.value } : p))
                      }}
                      className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      placeholder="Type a Gemini model id…"
                    />
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>Groq model</Label>
                  <Select
                    value={groqModelMode}
                    onValueChange={(v) => {
                      if (!v) return
                      setGroqModelMode(v)
                      const next = v === CUSTOM ? (groqCustomModel || form.groq_model) : v
                      setForm((p) => (p ? { ...p, groq_model: next } : p))
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent align="start">
                      {GROQ_MODELS.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.label}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM}>Custom model…</SelectItem>
                    </SelectContent>
                  </Select>
                  {groqModelMode === CUSTOM && (
                    <input
                      value={groqCustomModel}
                      onChange={(e) => {
                        setGroqCustomModel(e.target.value)
                        setForm((p) => (p ? { ...p, groq_model: e.target.value } : p))
                      }}
                      className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      placeholder="Type a Groq model id…"
                    />
                  )}
                </div>
              </div>
            </section>

            <section className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scheduling</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
                <div className="space-y-1.5">
                  <Label>Daily scrape time (HH:MM)</Label>
                  <input
                    value={form.scrape_schedule_time}
                    onChange={(e) =>
                      setForm((p) => (p ? { ...p, scrape_schedule_time: e.target.value } : p))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="03:00"
                  />
                </div>
                <div className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-semibold">Tip</span>
                  <span>Local time, 24-hour format.</span>
                </div>
              </div>
            </section>

            <section className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scraper tuning</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Location</Label>
                  <input
                    value={form.scrape_location}
                    onChange={(e) => setForm((p) => (p ? { ...p, scrape_location: e.target.value } : p))}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="Boise Idaho"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Max results per category</Label>
                  <input
                    value={String(form.scrape_max_results)}
                    onChange={(e) =>
                      setForm((p) =>
                        p
                          ? {
                              ...p,
                              scrape_max_results: Number(e.target.value || 0),
                            }
                          : p,
                      )
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    type="number"
                    min={1}
                    max={500}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>User agent override (optional)</Label>
                  <input
                    value={form.scrape_user_agent}
                    onChange={(e) =>
                      setForm((p) => (p ? { ...p, scrape_user_agent: e.target.value } : p))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="Leave blank to rotate…"
                  />
                </div>
                <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-foreground">Headless</p>
                    <p className="text-xs text-muted-foreground">Turn off to watch the browser.</p>
                  </div>
                  <button
                    onClick={() => setForm((p) => (p ? { ...p, scrape_headless: !p.scrape_headless } : p))}
                    className={`h-7 w-12 rounded-full transition-colors ${
                      form.scrape_headless ? 'bg-indigo-600' : 'bg-gray-300'
                    }`}
                    type="button"
                    aria-label="Toggle headless mode"
                  >
                    <span
                      className={`block h-6 w-6 bg-background rounded-full shadow transform transition-transform ${
                        form.scrape_headless ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </section>

            <section className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Outreach SMTP
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Auto-send enabled (env gate)</Label>
                  <button
                    type="button"
                    onClick={() =>
                      setForm((p) => (p ? { ...p, outreach_send_enabled: !p.outreach_send_enabled } : p))
                    }
                    className={`h-7 w-12 rounded-full transition-colors ${
                      form.outreach_send_enabled ? 'bg-indigo-600' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`block h-6 w-6 bg-background rounded-full shadow transform transition-transform ${
                        form.outreach_send_enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
                <div className="space-y-1.5">
                  <Label>Sender name</Label>
                  <input
                    value={form.outreach_sender_name}
                    onChange={(e) =>
                      setForm((p) => (p ? { ...p, outreach_sender_name: e.target.value } : p))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="Boise Web Studio"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Sender email</Label>
                  <input
                    value={form.outreach_sender_email}
                    onChange={(e) =>
                      setForm((p) => (p ? { ...p, outreach_sender_email: e.target.value } : p))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="you@example.com"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>SMTP host</Label>
                  <input
                    value={form.smtp_host}
                    onChange={(e) => setForm((p) => (p ? { ...p, smtp_host: e.target.value } : p))}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="smtp.gmail.com"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label>SMTP port</Label>
                  <input
                    value={String(form.smtp_port)}
                    onChange={(e) =>
                      setForm((p) =>
                        p
                          ? {
                              ...p,
                              smtp_port: Number(e.target.value || 0),
                            }
                          : p,
                      )
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    type="number"
                    min={1}
                    max={65535}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>SMTP username</Label>
                  <input
                    value={form.smtp_username}
                    onChange={(e) =>
                      setForm((p) => (p ? { ...p, smtp_username: e.target.value } : p))
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="you@example.com"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>SMTP password</Label>
                  <input
                    value={smtpPassword}
                    onChange={(e) => setSmtpPassword(e.target.value)}
                    type="password"
                    autoComplete="off"
                    placeholder={form.smtp_password_set ? 'Set (leave blank to keep)' : 'Paste password…'}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-foreground">SMTP TLS</p>
                  <p className="text-xs text-muted-foreground">Enable STARTTLS for SMTP transport.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setForm((p) => (p ? { ...p, smtp_use_tls: !p.smtp_use_tls } : p))}
                  className={`h-7 w-12 rounded-full transition-colors ${
                    form.smtp_use_tls ? 'bg-indigo-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`block h-6 w-6 bg-background rounded-full shadow transform transition-transform ${
                      form.smtp_use_tls ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </section>

            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Outreach Guardrails
                </p>
                {usage && (
                  <span className="text-xs text-muted-foreground">
                    Sent today: {usage.sent_today}/{usage.daily_cap} ({usage.timezone})
                  </span>
                )}
              </div>
              {!policyForm ? (
                <div className="text-sm text-muted-foreground">Loading guardrail policy…</div>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>Policy enabled</Label>
                      <button
                        type="button"
                        onClick={() =>
                          setPolicyForm((p) => (p ? { ...p, outreach_enabled: !p.outreach_enabled } : p))
                        }
                        className={`h-7 w-12 rounded-full transition-colors ${
                          policyForm.outreach_enabled ? 'bg-indigo-600' : 'bg-gray-300'
                        }`}
                      >
                        <span
                          className={`block h-6 w-6 bg-background rounded-full shadow transform transition-transform ${
                            policyForm.outreach_enabled ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Daily send cap</Label>
                      <input
                        value={String(policyForm.outreach_daily_send_cap)}
                        onChange={(e) =>
                          setPolicyForm((p) =>
                            p
                              ? {
                                  ...p,
                                  outreach_daily_send_cap: Number(e.target.value || 0),
                                }
                              : p,
                          )
                        }
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        type="number"
                        min={1}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1.5">
                      <Label>Window start (HH:MM)</Label>
                      <input
                        value={policyForm.outreach_send_window_start}
                        onChange={(e) =>
                          setPolicyForm((p) =>
                            p ? { ...p, outreach_send_window_start: e.target.value } : p,
                          )
                        }
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Window end (HH:MM)</Label>
                      <input
                        value={policyForm.outreach_send_window_end}
                        onChange={(e) =>
                          setPolicyForm((p) =>
                            p ? { ...p, outreach_send_window_end: e.target.value } : p,
                          )
                        }
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Timezone</Label>
                      <input
                        value={policyForm.outreach_send_timezone}
                        onChange={(e) =>
                          setPolicyForm((p) =>
                            p ? { ...p, outreach_send_timezone: e.target.value } : p,
                          )
                        }
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        placeholder="America/Boise"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <ToggleRow
                      label="Enforce send window"
                      value={policyForm.outreach_enforce_window}
                      onToggle={() =>
                        setPolicyForm((p) =>
                          p ? { ...p, outreach_enforce_window: !p.outreach_enforce_window } : p,
                        )
                      }
                    />
                    <ToggleRow
                      label="Enforce daily cap"
                      value={policyForm.outreach_enforce_daily_cap}
                      onToggle={() =>
                        setPolicyForm((p) =>
                          p
                            ? { ...p, outreach_enforce_daily_cap: !p.outreach_enforce_daily_cap }
                            : p,
                        )
                      }
                    />
                    <ToggleRow
                      label="Enforce suppression"
                      value={policyForm.outreach_enforce_suppression}
                      onToggle={() =>
                        setPolicyForm((p) =>
                          p
                            ? { ...p, outreach_enforce_suppression: !p.outreach_enforce_suppression }
                            : p,
                        )
                      }
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Allowed lead statuses</Label>
                    <div className="flex flex-wrap gap-2">
                      {(['new', 'reviewed', 'interested', 'archived'] as const).map((status) => {
                        const active = policyForm.outreach_allowed_statuses.includes(status)
                        return (
                          <button
                            key={status}
                            type="button"
                            onClick={() =>
                              setPolicyForm((p) => {
                                if (!p) return p
                                const has = p.outreach_allowed_statuses.includes(status)
                                return {
                                  ...p,
                                  outreach_allowed_statuses: has
                                    ? p.outreach_allowed_statuses.filter((s) => s !== status)
                                    : [...p.outreach_allowed_statuses, status],
                                }
                              })
                            }
                            className={`rounded-md border px-2.5 py-1 text-xs capitalize ${
                              active
                                ? 'bg-indigo-600 text-white border-indigo-600'
                                : 'bg-background text-muted-foreground border-border'
                            }`}
                          >
                            {status}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => policyMutation.mutate()}
                      disabled={policyMutation.isPending}
                    >
                      {policyMutation.isPending ? 'Saving guardrails…' : 'Save guardrails'}
                    </Button>
                  </div>
                </>
              )}
            </section>

            <section className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Suppression list
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
                <input
                  value={suppressionEmail}
                  onChange={(e) => setSuppressionEmail(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="email@example.com"
                />
                <input
                  value={suppressionReason}
                  onChange={(e) => setSuppressionReason(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="Reason (optional)"
                />
                <Button
                  size="sm"
                  onClick={() => addSuppressionMutation.mutate()}
                  disabled={addSuppressionMutation.isPending || !suppressionEmail.trim()}
                >
                  Add
                </Button>
              </div>
              <div className="max-h-44 overflow-auto rounded-md border border-border">
                {(suppressions ?? []).length === 0 ? (
                  <div className="p-3 text-sm text-muted-foreground">No suppressions yet.</div>
                ) : (
                  <div className="divide-y">
                    {(suppressions ?? []).map((item) => (
                      <div key={item.id} className="p-3 flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">{item.email}</p>
                          {item.reason && <p className="text-xs text-muted-foreground">{item.reason}</p>}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => removeSuppressionMutation.mutate(item.id)}
                          disabled={removeSuppressionMutation.isPending}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            {(errorMsg || policyError) && (
              <p className="text-sm text-red-500">{errorMsg ?? policyError}</p>
            )}
          </div>
        )}

        <DialogFooter className="mt-4 gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!canSave || mutation.isPending || isLoading}>
            {mutation.isPending ? 'Saving…' : 'Save changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ToggleRow({
  label,
  value,
  onToggle,
}: {
  label: string
  value: boolean
  onToggle: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <button
        type="button"
        onClick={onToggle}
        className={`h-7 w-12 rounded-full transition-colors ${value ? 'bg-indigo-600' : 'bg-gray-300'}`}
      >
        <span
          className={`block h-6 w-6 bg-background rounded-full shadow transform transition-transform ${
            value ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )
}

