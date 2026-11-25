import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Copy,
  Inbox,
  Search,
  Sparkles,
  UserCheck,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useTicketCounts, useTickets, useUpdateTicketStatus } from '@/hooks/queries'
import { cn, formatDate, formatRelativeTime } from '@/lib/utils'
import type { Ticket, TicketStatus, TicketUrgency } from '@/types'

const QUEUE_TABS: { key: string; label: string; countKey: string }[] = [
  { key: 'all', label: 'Active', countKey: 'active' },
  { key: 'needs_human', label: 'Needs human', countKey: 'needs_human' },
  { key: 'open', label: 'Open', countKey: 'open' },
  { key: 'escalated', label: 'Escalated', countKey: 'escalated' },
  { key: 'resolved', label: 'Resolved', countKey: 'resolved' },
]

const URGENCY_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All urgencies' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

/** Live support desk: stat strip, filterable queue, polling, detail panel. */
export default function TicketsPage() {
  const [tab, setTab] = useState('all')
  const [urgency, setUrgency] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)

  // Debounce the search box so typing does not spam the API.
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const filters =
    tab === 'needs_human'
      ? { needs_human: true, urgency, search }
      : tab === 'all'
        ? { urgency, search }
        : { status: tab, urgency, search }

  // A support desk is live: poll the queue every 15s and the counters every 20s.
  const { data: tickets, isPending } = useTickets(filters, { refetchInterval: 15_000 })
  const { data: counts } = useTicketCounts()

  // Prefer the fresh row from the polled list; fall back to the stored object
  // so the detail panel stays stable when the ticket leaves the current filter
  // (e.g. it was just resolved while the "Active" tab is open).
  const selected = useMemo(() => {
    const fresh = tickets?.find((t) => t.id === selectedTicket?.id)
    return fresh ?? selectedTicket
  }, [tickets, selectedTicket])

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-border bg-card/40 px-6 py-6 backdrop-blur md:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="micro-label flex items-center gap-1.5">
            <Sparkles className="size-3 text-primary" /> AI classification · extraction · escalation
          </p>
          <h1 className="mt-1 font-display text-3xl">
            Ticket <span className="italic text-primary">triage</span>
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Every chat can escalate into a ticket — the AI classifies, extracts and
            drafts; this desk routes what needs a human. Live view, refreshes every 15s.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8 md:px-8">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="Needs human"
            value={counts?.needs_human ?? 0}
            icon={<UserCheck className="size-4" />}
            tone={counts?.needs_human ? 'bad' : 'good'}
            hint="AI-flagged escalations waiting"
          />
          <StatCard label="Open" value={counts?.open ?? 0} icon={<Inbox className="size-4" />} />
          <StatCard
            label="Escalated"
            value={counts?.escalated ?? 0}
            icon={<AlertTriangle className="size-4" />}
            tone={counts?.escalated ? 'warn' : 'neutral'}
          />
          <StatCard
            label="Resolved"
            value={counts?.resolved ?? 0}
            icon={<CheckCircle2 className="size-4" />}
            tone="good"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <QueueCard
              tab={tab}
              onTab={setTab}
              urgency={urgency}
              onUrgency={setUrgency}
              searchInput={searchInput}
              onSearchInput={setSearchInput}
              counts={counts ?? {}}
              tickets={tickets ?? []}
              isPending={isPending}
              selectedId={selected?.id ?? null}
              onSelect={setSelectedTicket}
            />
          </div>

          <div className="lg:col-span-7">
            {selected ? (
              <TicketDetail key={selected.id} ticket={selected} onUpdated={setSelectedTicket} />
            ) : (
              <div className="flex h-full min-h-72 flex-col items-center justify-center rounded-md border border-dashed border-border p-10 text-center">
                <Inbox className="size-8 text-muted-foreground" />
                <p className="mt-3 font-display text-lg">Select a ticket</p>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Tickets are created from the support chat — open a conversation and
                  choose <span className="text-primary">Create support ticket</span> (or
                  escalate a not-grounded answer). Pick one here to see the full
                  classification, extracted facts and the suggested reply.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  tone = 'neutral',
  hint,
}: {
  label: string
  value: number
  icon?: ReactNode
  tone?: 'good' | 'warn' | 'bad' | 'neutral'
  hint?: string
}) {
  const toneClass =
    tone === 'good'
      ? 'text-success'
      : tone === 'warn'
        ? 'text-warning'
        : tone === 'bad'
          ? 'text-destructive'
          : ''
  return (
    <div
      className={cn(
        'rounded-md border p-4',
        tone === 'bad' ? 'border-destructive/30 bg-destructive/5' : 'border-border bg-card/50',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="micro-label">{label}</span>
        {icon && <span className={toneClass}>{icon}</span>}
      </div>
      <p className={cn('mt-2 font-display text-2xl', toneClass)}>{value.toLocaleString()}</p>
      {hint && <p className="micro-label mt-1 !text-[9px] normal-case">{hint}</p>}
    </div>
  )
}

function QueueCard({
  tab,
  onTab,
  urgency,
  onUrgency,
  searchInput,
  onSearchInput,
  counts,
  tickets,
  isPending,
  selectedId,
  onSelect,
}: {
  tab: string
  onTab: (tab: string) => void
  urgency: string
  onUrgency: (urgency: string) => void
  searchInput: string
  onSearchInput: (value: string) => void
  counts: Record<string, number>
  tickets: Ticket[]
  isPending: boolean
  selectedId: string | null
  onSelect: (ticket: Ticket) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ClipboardList className="size-4 text-primary" /> Queue
        </CardTitle>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {QUEUE_TABS.map((item) => {
            const count = counts[item.countKey]
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onTab(item.key)}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                  tab === item.key
                    ? 'border-primary/40 bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground',
                )}
              >
                {item.label}
                {typeof count === 'number' && (
                  <span className={cn('ml-1.5 font-mono', tab === item.key ? 'text-primary/80' : 'text-muted-foreground/60')}>
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        <div className="mt-2 flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(event) => onSearchInput(event.target.value)}
              placeholder="Search summary, message, category…"
              className="h-8 pl-8 text-xs"
              aria-label="Search tickets"
            />
          </div>
          <select
            value={urgency}
            onChange={(event) => onUrgency(event.target.value)}
            aria-label="Filter by urgency"
            className="h-8 rounded-sm border border-border bg-card px-2 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            {URGENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {isPending ? (
          <>
            <div className="h-16 animate-pulse rounded-md bg-muted/60" />
            <div className="h-16 animate-pulse rounded-md bg-muted/60" />
          </>
        ) : tickets.length === 0 ? (
          <div className="py-8 text-center">
            <Inbox className="mx-auto size-6 text-muted-foreground/70" />
            <p className="mt-2 text-sm text-muted-foreground">
              {searchInput || urgency
                ? 'No tickets match the current filters.'
                : 'The queue is clear — escalate a chat to see it here.'}
            </p>
          </div>
        ) : (
          tickets.map((ticket) => (
            <QueueRow
              key={ticket.id}
              ticket={ticket}
              selected={ticket.id === selectedId}
              onSelect={() => onSelect(ticket)}
            />
          ))
        )}
      </CardContent>
    </Card>
  )
}

const URGENCY_STRIPE: Record<TicketUrgency, string> = {
  critical: 'border-l-destructive',
  high: 'border-l-warning',
  medium: 'border-l-primary/50',
  low: 'border-l-muted-foreground/40',
}

function QueueRow({
  ticket,
  selected,
  onSelect,
}: {
  ticket: Ticket
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-md border border-l-2 px-3 py-2.5 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        selected ? 'border-primary/40 bg-primary/5' : 'border-border hover:border-primary/30 hover:bg-accent/40',
        URGENCY_STRIPE[ticket.urgency] ?? 'border-l-muted-foreground/40',
      )}
    >
      <div className="flex items-center gap-1.5">
        <UrgencyBadge urgency={ticket.urgency} />
        <Badge variant={sentimentVariant(ticket.sentiment)}>{ticket.sentiment}</Badge>
        <Badge variant="outline">{categoryLabel(ticket.category)}</Badge>
        {ticket.needs_human && (
          <Badge variant="destructive" className="ml-auto">
            <UserCheck className="size-3" /> human
          </Badge>
        )}
      </div>
      <p className="mt-1.5 truncate text-sm">{ticket.summary}</p>
      <p className="micro-label mt-1 flex items-center gap-1.5 truncate">
        <span>{ticket.product_name ?? 'no product'}</span>
        <span>·</span>
        <span>{formatRelativeTime(ticket.created_at)}</span>
        {ticket.created_by_name && (
          <>
            <span>·</span>
            <span className="truncate">via {ticket.created_by_name}</span>
          </>
        )}
      </p>
    </button>
  )
}

function UrgencyBadge({ urgency }: { urgency: TicketUrgency }) {
  const variant =
    urgency === 'critical'
      ? 'destructive'
      : urgency === 'high'
        ? 'warning'
        : urgency === 'medium'
          ? 'secondary'
          : 'outline'
  return <Badge variant={variant}>{urgency}</Badge>
}

function sentimentVariant(sentiment: string) {
  if (sentiment === 'angry') return 'destructive'
  if (sentiment === 'frustrated') return 'warning'
  if (sentiment === 'concerned') return 'secondary'
  return 'outline'
}

function categoryLabel(category: string): string {
  return category
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' · ')
}

/** Resolve / dismiss capture a note (the backend stores it); escalate is instant. */
function StatusDialog({
  ticket,
  targetStatus,
  onClose,
  onUpdated,
}: {
  ticket: Ticket
  targetStatus: 'resolved' | 'dismissed'
  onClose: () => void
  onUpdated: (ticket: Ticket) => void
}) {
  const updateStatus = useUpdateTicketStatus()
  const [note, setNote] = useState('')

  const submit = async () => {
    try {
      const updated = await updateStatus.mutateAsync({
        id: ticket.id,
        status: targetStatus,
        resolution_note: note.trim() || undefined,
      })
      toast.success(`Ticket ${targetStatus}`)
      onUpdated(updated)
      onClose()
    } catch (error) {
      toast.error('Update failed', { description: (error as Error).message })
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>
            {targetStatus === 'resolved' ? 'Resolve ticket' : 'Dismiss ticket'}
          </DialogTitle>
          <DialogDescription>
            {targetStatus === 'resolved'
              ? 'Add a short note about the outcome (stored with the ticket).'
              : 'Optionally note why this ticket is being dismissed.'}
          </DialogDescription>
        </DialogHeader>
        <Textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={3}
          maxLength={2000}
          placeholder="Resolution note…"
          aria-label="Resolution note"
          autoFocus
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={updateStatus.isPending}>
            Confirm {targetStatus}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TicketDetail({
  ticket,
  onUpdated,
}: {
  ticket: Ticket
  onUpdated: (ticket: Ticket) => void
}) {
  const updateStatus = useUpdateTicketStatus()
  const [copiedMessage, setCopiedMessage] = useState(false)
  const [statusTarget, setStatusTarget] = useState<'resolved' | 'dismissed' | null>(null)

  const setStatus = async (status: TicketStatus) => {
    try {
      const updated = await updateStatus.mutateAsync({ id: ticket.id, status })
      toast.success(`Ticket ${status}`)
      onUpdated(updated)
    } catch (error) {
      toast.error('Update failed', { description: (error as Error).message })
    }
  }

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedMessage(true)
      window.setTimeout(() => setCopiedMessage(false), 1600)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={ticket.status === 'resolved' ? 'success' : ticket.status === 'escalated' ? 'destructive' : 'secondary'}>
            {ticket.status}
          </Badge>
          <UrgencyBadge urgency={ticket.urgency} />
          <Badge variant={sentimentVariant(ticket.sentiment)}>{ticket.sentiment}</Badge>
          <Badge variant="outline">{categoryLabel(ticket.category)}</Badge>
          {ticket.triage_latency_ms != null && (
            <span className="micro-label ml-auto">{(ticket.triage_latency_ms / 1000).toFixed(1)}s triage</span>
          )}
        </div>
        <CardTitle className="pt-2 text-xl leading-snug">{ticket.summary}</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2">
          <span>{ticket.product_name ?? 'no product context'}</span>
          <span>·</span>
          <span title={formatDate(ticket.created_at)}>{formatRelativeTime(ticket.created_at)}</span>
          {ticket.created_by_name && (
            <>
              <span>·</span>
              <span>via {ticket.created_by_name}</span>
            </>
          )}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {ticket.needs_human && (
          <div className="flex items-start gap-2.5 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
            <div>
              <p className="text-sm font-medium text-destructive">Human agent required</p>
              {ticket.escalation_reason && (
                <p className="mt-0.5 text-xs text-destructive/80">{ticket.escalation_reason}</p>
              )}
            </div>
          </div>
        )}

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="micro-label">Customer message</p>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-2 text-xs"
              onClick={() => void copy(ticket.raw_message)}
            >
              {copiedMessage ? <CheckCircle2 className="size-3 text-success" /> : <Copy className="size-3" />}
              {copiedMessage ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <p className="rounded-md border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed">
            {ticket.raw_message}
          </p>
        </div>

        <div>
          <p className="micro-label mb-2">Extracted data</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <ExtractedField label="Product" value={ticket.extracted_data?.product} />
            <ExtractedField label="Issue" value={ticket.extracted_data?.issue} />
            <ExtractedField label="Requested action" value={ticket.extracted_data?.requested_action} />
          </div>
          {(ticket.extracted_data?.topics?.length ?? 0) > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {ticket.extracted_data.topics.map((topic) => (
                <Badge key={topic} variant="outline">
                  {topic}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {ticket.resolution_note && (
          <div>
            <p className="micro-label mb-2">Resolution note</p>
            <p className="text-sm text-muted-foreground">{ticket.resolution_note}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          {ticket.status !== 'escalated' && ticket.status !== 'resolved' && (
            <Button variant="outline" size="sm" onClick={() => void setStatus('escalated')} disabled={updateStatus.isPending}>
              <UserCheck className="size-3.5" /> Escalate
            </Button>
          )}
          {ticket.status !== 'resolved' && (
            <Button size="sm" onClick={() => setStatusTarget('resolved')} disabled={updateStatus.isPending}>
              <CheckCircle2 className="size-3.5" /> Mark resolved
            </Button>
          )}
          {ticket.status !== 'dismissed' && (
            <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setStatusTarget('dismissed')} disabled={updateStatus.isPending}>
              Dismiss
            </Button>
          )}
          {(ticket.status === 'resolved' || ticket.status === 'dismissed') && (
            <Button variant="ghost" size="sm" onClick={() => void setStatus('open')} disabled={updateStatus.isPending}>
              Reopen
            </Button>
          )}
        </div>
      </CardContent>

      {statusTarget && (
        <StatusDialog
          ticket={ticket}
          targetStatus={statusTarget}
          onClose={() => setStatusTarget(null)}
          onUpdated={onUpdated}
        />
      )}
    </Card>
  )
}

function ExtractedField({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <p className="micro-label">{label}</p>
      <p className={cn('mt-1 text-sm', value ? '' : 'italic text-muted-foreground/60')}>{value ?? 'not stated'}</p>
    </div>
  )
}
