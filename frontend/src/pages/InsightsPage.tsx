import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  Bot,
  BrainCircuit,
  CircleAlert,
  Gauge,
  ListChecks,
  MessageSquare,
  ShieldQuestion,
  Timer,
  TrendingUp,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalyticsOverview } from '@/hooks/queries'
import { useAuthStore } from '@/stores/authStore'
import { cn, formatDate } from '@/lib/utils'
import type { KnowledgeGap, ProductAnalytics, TopQuestion } from '@/types'

export default function InsightsPage() {
  const isAdmin = useAuthStore((s) => s.user?.role === 'admin')
  const { data, isPending } = useAnalyticsOverview(isAdmin)

  if (!isAdmin) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="flex size-12 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/30">
          <ShieldQuestion className="size-6 text-primary" />
        </div>
        <div>
          <p className="font-display text-2xl">Admin area</p>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            AI insights are available to workspace administrators only.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-border bg-card/40 px-6 py-6 backdrop-blur md:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="micro-label">AI · continuous improvement</p>
          <h1 className="mt-1 font-display text-3xl">
            Support <span className="italic text-primary">insights</span>
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            How well the bot answers from the manuals — and exactly where the knowledge
            gaps are, so you know which documentation to add next.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-6 px-6 py-8 md:px-8">
        {isPending || !data ? (
          <SkeletonGrid />
        ) : (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Kpi label="Conversations" value={data.totals.conversations.toLocaleString()} icon={<MessageSquare className="size-4 text-primary" />} />
              <Kpi label="Questions answered" value={data.totals.assistant_answers.toLocaleString()} icon={<ListChecks className="size-4 text-primary" />} />
              <Kpi
                label="Grounding rate"
                value={data.totals.grounded_rate == null ? '—' : `${Math.round(data.totals.grounded_rate * 100)}%`}
                icon={<TrendingUp className="size-4 text-primary" />}
                tone={groundedTone(data.totals.grounded_rate)}
                hint={data.totals.grounded_rate == null ? 'no answers yet' : 'answers grounded in manuals'}
              />
              <Kpi
                label="Avg confidence"
                value={data.totals.avg_confidence == null ? '—' : `${Math.round(data.totals.avg_confidence * 100)}%`}
                icon={<Gauge className="size-4 text-primary" />}
              />
              <Kpi
                label="Avg answer time"
                value={data.totals.avg_latency_ms == null ? '—' : `${(data.totals.avg_latency_ms / 1000).toFixed(1)}s`}
                icon={<Timer className="size-4 text-primary" />}
              />
            </div>

            <PerProductCard data={data.per_product} />
            <div className="grid gap-6 lg:grid-cols-2">
              <KnowledgeGapsCard gaps={data.knowledge_gaps} />
              <TopQuestionsCard questions={data.top_questions} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function groundedTone(rate: number | null): 'good' | 'warn' | 'bad' | 'neutral' {
  if (rate == null) return 'neutral'
  if (rate >= 0.85) return 'good'
  if (rate >= 0.6) return 'warn'
  return 'bad'
}

function Kpi({
  label,
  value,
  icon,
  tone = 'neutral',
  hint,
}: {
  label: string
  value: string
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
    <div className="rounded-md border border-border bg-card/50 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="micro-label">{label}</span>
        {icon}
      </div>
      <p className={cn('mt-2 font-display text-2xl', toneClass)}>{value}</p>
      {hint && <p className="micro-label mt-1 !text-[9px] normal-case">{hint}</p>}
    </div>
  )
}

function SkeletonGrid() {
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-56" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </>
  )
}

function PerProductCard({ data }: { data: ProductAnalytics[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <BrainCircuit className="size-4 text-primary" /> Per-product performance
        </CardTitle>
        <CardDescription>Where conversations happen and how well they are grounded.</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No products yet.</p>
        ) : (
          <div className="overflow-hidden rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left">
                  <th className="micro-label px-4 py-2.5">Product</th>
                  <th className="micro-label px-4 py-2.5">Conversations</th>
                  <th className="micro-label px-4 py-2.5">Questions</th>
                  <th className="micro-label px-4 py-2.5">Avg confidence</th>
                  <th className="micro-label px-4 py-2.5">Unanswered</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {data.map((row) => (
                  <tr key={row.product_id} className="border-b border-border/60 last:border-0 hover:bg-accent/40">
                    <td className="px-4 py-2.5">{row.product_name}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{row.conversations}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{row.questions}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">
                      {row.avg_confidence == null ? '—' : `${Math.round(row.avg_confidence * 100)}%`}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn('font-mono text-xs', row.unanswered > 0 ? 'text-warning' : 'text-muted-foreground')}>
                        {row.unanswered}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link
                        to={`/products/${row.product_id}`}
                        className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
                      >
                        Manuals <ArrowUpRight className="size-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
function KnowledgeGapsCard({ gaps }: { gaps: KnowledgeGap[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <CircleAlert className="size-4 text-warning" /> Knowledge gaps
        </CardTitle>
        <CardDescription>
          Questions the bot could not answer from the manuals — add documentation for these.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {gaps.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-6 text-center">
            <Bot className="mx-auto size-6 text-success" />
            <p className="mt-2 text-sm text-muted-foreground">
              No gaps — every question was answered from the manuals.
            </p>
          </div>
        ) : (
          gaps.map((gap) => (
            <div key={gap.conversation_id} className="rounded-md border border-warning/25 bg-warning/5 px-3.5 py-3">
              <p className="text-sm">“{gap.question}”</p>
              <p className="mt-1 line-clamp-1 text-xs italic text-muted-foreground">{gap.answer_preview}</p>
              <p className="micro-label mt-1.5 flex items-center gap-2">
                <span>{gap.product_name ?? 'archived product'}</span>
                <span>·</span>
                <span>{formatDate(gap.created_at)}</span>
                {gap.confidence != null && (
                  <>
                    <span>·</span>
                    <span className="text-warning/80">{Math.round(gap.confidence * 100)}% conf.</span>
                  </>
                )}
              </p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}

function TopQuestionsCard({ questions }: { questions: TopQuestion[] }) {
  const max = Math.max(1, ...questions.map((q) => q.count))
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ListChecks className="size-4 text-primary" /> Most asked questions
        </CardTitle>
        <CardDescription>Exact repeats across the workspace — candidates for quick answers.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {questions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No questions asked yet.</p>
        ) : (
          questions.map((item) => (
            <div key={item.question}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 flex-1 truncate text-sm">{item.question}</p>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">×{item.count}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: `${(item.count / max) * 100}%` }}
                />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
