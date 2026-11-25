import { Bot, Loader2, Waypoints } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { SourceChips } from '@/components/chat/SourceChips'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chatStore'
import type { ChatStage } from '@/types'

const STAGE_LABELS: Record<ChatStage, string> = {
  understanding_question: 'Understanding the question…',
  searching_manual: 'Searching the manual…',
  generating_answer: 'Composing a grounded answer…',
}

export function StreamingPanel() {
  const stage = useChatStore((s) => s.stage)
  const sources = useChatStore((s) => s.streamingSources)
  const pendingUserMessage = useChatStore((s) => s.pendingUserMessage)
  const streamedContent = useChatStore((s) => s.streamedContent)

  return (
    <div className="flex gap-3 animate-rise">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-primary/15 ring-1 ring-primary/30">
        <Bot className="size-4 text-primary" />
      </div>
      <div className="min-w-0 max-w-[85%] flex-1">
        <p className="micro-label mb-1.5">SmartSupport</p>
        <div className="rounded-md border border-border bg-card px-4 py-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-primary" />
            <span className="caret">{stage ? STAGE_LABELS[stage] : 'Connecting…'}</span>
          </div>
          {pendingUserMessage && (
            <p className="mt-2 truncate font-mono text-[11px] text-muted-foreground/70">“{pendingUserMessage}”</p>
          )}
          {sources.length > 0 && (
            <div className="mt-2 flex items-center gap-1.5">
              <Waypoints className="size-3 text-primary/70" />
              <span className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                {sources.length} excerpt{sources.length === 1 ? '' : 's'} retrieved
              </span>
            </div>
          )}
          {/* Live answer draft — rendered progressively as tokens arrive. */}
          {streamedContent && (
            <div className="mt-3 border-t border-border pt-3 text-sm leading-relaxed [&_a]:text-primary [&_code]:rounded-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-[13px] [&_li]:ml-4 [&_li]:list-disc [&_ol]:space-y-1 [&_ol_>li]:list-decimal [&_p]:my-1 [&_strong]:text-foreground [&_ul]:space-y-1">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamedContent}</ReactMarkdown>
            </div>
          )}
        </div>
        {sources.length > 0 && (
          <div className={cn('max-w-lg text-left')}>
            <SourceChips sources={sources} />
          </div>
        )}
      </div>
    </div>
  )
}
