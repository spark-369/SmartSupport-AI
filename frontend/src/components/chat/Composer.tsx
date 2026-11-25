import { useEffect, useRef, useState } from 'react'
import { Send, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface ComposerProps {
  disabled?: boolean
  isStreaming: boolean
  onSend: (content: string) => void
  onCancel: () => void
}

const MAX_LEN = 4000

export function Composer({ disabled, isStreaming, onSend, onCancel }: ComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Focus the composer whenever it becomes usable (conversation selected).
  useEffect(() => {
    if (!disabled) textareaRef.current?.focus()
  }, [disabled])

  const submit = () => {
    const content = value.trim()
    if (!content || disabled || isStreaming) return
    onSend(content)
    setValue('')
  }

  // Auto-grow the textarea with content (capped at max-h-40).
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [value])

  const nearLimit = value.length > MAX_LEN * 0.9

  return (
    <div className="border-t border-border bg-card/70 p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <Textarea
          ref={textareaRef}
          value={value}
          maxLength={MAX_LEN}
          rows={1}
          disabled={disabled}
          placeholder={
            disabled ? 'Select or start a conversation first…' : 'Ask about setup, brewing, cleaning, error codes…'
          }
          className="max-h-40 min-h-11 resize-none py-3"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        {isStreaming ? (
          <Button variant="outline" size="icon" className="h-11 w-11" onClick={onCancel} title="Stop" aria-label="Stop generating">
            <Square className="size-4 text-destructive" />
          </Button>
        ) : (
          <Button size="icon" className="h-11 w-11" onClick={submit} disabled={disabled || !value.trim()} aria-label="Send message">
            <Send className="size-4" />
          </Button>
        )}
      </div>
      <p
        className={cn(
          'mx-auto mt-2 max-w-3xl text-right font-mono text-[10px]',
          nearLimit ? 'text-warning' : 'text-muted-foreground/60',
        )}
      >
        {value.length}/{MAX_LEN} · Enter to send · Shift+Enter for newline
      </p>
    </div>
  )
}
