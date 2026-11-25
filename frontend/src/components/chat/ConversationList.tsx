import { useState } from 'react'
import { MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DeleteConversationDialog,
  RenameConversationDialog,
} from '@/components/chat/ConversationDialogs'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chatStore'
import type { Conversation } from '@/types'

interface ConversationListProps {
  conversations: Conversation[]
  onStarted?: () => void
  /** Invoked after a conversation is selected (e.g. close the mobile drawer). */
  onAfterSelect?: () => void
}

export function ConversationList({ conversations, onStarted, onAfterSelect }: ConversationListProps) {
  const activeId = useChatStore((s) => s.activeConversationId)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)

  const [renaming, setRenaming] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState<Conversation | null>(null)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3">
        <span className="micro-label">Conversations</span>
        {onStarted && (
          <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={onStarted}>
            <Plus className="size-3.5" /> New
          </Button>
        )}
      </div>
      <ScrollArea className="flex-1 px-2 pb-3">
        <div className="space-y-1">
          {conversations.length === 0 && (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              No conversations yet.
              <br />
              Ask your first question.
            </p>
          )}
          {conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              conversation={conversation}
              active={conversation.id === activeId}
              onSelect={() => {
                setActiveConversation(conversation.id)
                onAfterSelect?.()
              }}
              onRename={() => setRenaming(conversation)}
              onDelete={() => setDeleting(conversation)}
            />
          ))}
        </div>
      </ScrollArea>

      {renaming && <RenameConversationDialog conversation={renaming} onClose={() => setRenaming(null)} />}
      {deleting && (
        <DeleteConversationDialog
          conversation={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={(deleted) => {
            if (deleted.id === activeId) setActiveConversation(null)
          }}
        />
      )}
    </div>
  )
}

function ConversationRow({
  conversation,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: Conversation
  active: boolean
  onSelect: () => void
  onRename: () => void
  onDelete: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        'group flex cursor-pointer items-center gap-1 rounded-sm px-2.5 py-2 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        active
          ? 'bg-primary/10 text-primary ring-1 ring-primary/25'
          : 'text-muted-foreground hover:bg-accent hover:text-foreground',
      )}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate">{conversation.title}</p>
        <p className="micro-label mt-0.5 truncate">
          {conversation.product_name ?? 'archived product'} · {conversation.message_count} msg
        </p>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            aria-label={`Actions for ${conversation.title}`}
            onClick={(event) => event.stopPropagation()}
          >
            <MoreHorizontal className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem
            onClick={(event) => {
              event.stopPropagation()
              onRename()
            }}
          >
            <Pencil className="size-3.5" /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(event) => {
              event.stopPropagation()
              onDelete()
            }}
          >
            <Trash2 className="size-3.5" /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
