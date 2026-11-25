import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertTriangle, Bot, Check, CheckCircle2, Copy, Sparkles, User, UserCheck } from 'lucide-react'

import { cn, formatTime } from '@/lib/utils'
import { useChatStore } from '@/stores/chatStore'
import { SourceChips } from '@/components/chat/SourceChips'
import type { Message } from '@/types'

interface MessageBubbleProps {
  message: Message
  /** Present → suggested follow-ups are rendered as clickable chips. */
  onFollowUp?: (question: string) => void
  /** Present → not-grounded answers offer a one-click human escalation. */
  onEscalate?: () => void
}

export function MessageBubble({ message, onFollowUp, onEscalate }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isStreaming = useChatStore((s) => s.isStreaming)
  const [copied, setCopied] = useState(false)

  const copyContent = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className={cn('group flex gap-3 animate-rise', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-sm ring-1',
          isUser ? 'bg-accent ring-border' : 'bg-primary/15 ring-primary/30',
        )}
      >
        {isUser ? <User className="size-4 text-foreground/80" /> : <Bot className="size-4 text-primary" />}
      </div>

      <div className={cn('min-w-0 max-w-[85%]', isUser && 'text-right')}>
        <p className="micro-label mb-1.5 flex items-center gap-2">
          <span>{isUser ? 'You' : 'SmartSupport'}</span>
          <span className="text-muted-foreground/50">{formatTime(message.created_at)}</span>
          {message.confidence != null && (
            <span className="text-primary/70">{Math.round(message.confidence * 100)}% confidence</span>
          )}
          {message.latency_ms != null && !isUser && (
            <span className="text-muted-foreground/60">{(message.latency_ms / 1000).toFixed(1)}s</span>
          )}
          {!isUser && (
            <button
              type="button"
              onClick={() => void copyContent()}
              aria-label={copied ? 'Copied' : 'Copy answer'}
              className="ml-auto inline-flex items-center gap-1 rounded-xs px-1 py-0.5 text-muted-foreground/50 transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60 outline-none"
            >
              {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />}
            </button>
          )}
        </p>

        <div
          className={cn(
            'inline-block max-w-full rounded-md border px-4 py-3 text-left text-sm leading-relaxed',
            isUser ? 'border-primary/25 bg-primary/10' : 'border-border bg-card',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <>
              {message.found_in_manual === false && (
                <div className="mb-2 flex items-start gap-2 rounded-xs border border-warning/30 bg-warning/10 px-2.5 py-2 text-xs text-warning">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p>Not found in the manual — please verify with official support.</p>
                    {onEscalate && (
                      <button
                        type="button"
                        onClick={onEscalate}
                        className="mt-1 inline-flex items-center gap-1 rounded-xs text-destructive underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/60"
                      >
                        <UserCheck className="size-3" /> Escalate to a human
                      </button>
                    )}
                  </div>
                </div>
              )}
              <div className="prose-invert space-y-2 [&_a]:text-primary [&_code]:rounded-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-[13px] [&_li]:ml-4 [&_li]:list-disc [&_ol_>li]:list-decimal [&_ol]:space-y-1 [&_strong]:text-foreground [&_ul]:space-y-1">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              </div>
              {message.found_in_manual === true && (
                <p className="mt-2 flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-success/80 uppercase">
                  <CheckCircle2 className="size-3" /> Grounded in manual
                </p>
              )}
            </>
          )}
        </div>

        {!isUser && <SourceChips sources={message.sources} />}

        {!isUser && onFollowUp && (message.follow_ups?.length ?? 0) > 0 && (
          <div className="mt-3 animate-rise">
            <p className="micro-label mb-2 flex items-center gap-1.5">
              <Sparkles className="size-3 text-primary/70" /> Suggested follow-ups
            </p>
            <div className="flex flex-wrap gap-1.5">
              {message.follow_ups.map((question) => (
                <button
                  key={question}
                  type="button"
                  disabled={isStreaming}
                  onClick={() => onFollowUp(question)}
                  className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs text-primary transition-colors outline-none hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none disabled:opacity-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
