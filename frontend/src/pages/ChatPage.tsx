import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowDown,
  Bot,
  MessagesSquare,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Sparkles,
  Ticket as TicketIcon,
  Trash2,
  User,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Composer } from '@/components/chat/Composer'
import {
  DeleteConversationDialog,
  RenameConversationDialog,
} from '@/components/chat/ConversationDialogs'
import { ConversationList } from '@/components/chat/ConversationList'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { StartConversationPanel } from '@/components/chat/StartConversationPanel'
import { StreamingPanel } from '@/components/chat/StreamingPanel'
import { useChatStream } from '@/hooks/useChatStream'
import {
  useConversation,
  useConversations,
  useCreateConversation,
  useCreateTicketFromConversation,
  useProducts,
} from '@/hooks/queries'
import { useChatStore } from '@/stores/chatStore'
import { useAuthStore } from '@/stores/authStore'
import type { Conversation } from '@/types'

const STARTER_PROMPTS = [
  'How do I get started?',
  'What maintenance is required?',
  'What do the error codes mean?',
]

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { data: products } = useProducts()
  const { data: conversations } = useConversations()
  const createConversation = useCreateConversation()
  const createTicket = useCreateTicketFromConversation()

  const activeId = useChatStore((s) => s.activeConversationId)
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)
  const error = useChatStore((s) => s.error)
  const pendingUserMessage = useChatStore((s) => s.pendingUserMessage)
  const lastQuestion = useChatStore((s) => s.lastQuestion)
  const queuedQuestion = useChatStore((s) => s.queuedQuestion)
  const setQueuedQuestion = useChatStore((s) => s.setQueuedQuestion)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [renaming, setRenaming] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState<Conversation | null>(null)

  // ?product=<id> → auto-start a conversation with that product (and ?q=… from
  // the search page's "Ask in chat" deep-link queues the question to auto-send).
  const targetProductId = searchParams.get('product')
  useEffect(() => {
    if (!targetProductId) return
    const question = searchParams.get('q')
    void createConversation
      .mutateAsync(targetProductId)
      .then((conversation) => {
        setActiveConversation(conversation.id)
        if (question) setQueuedQuestion(question)
      })
      .catch(() => undefined)
      .finally(() => setSearchParams({}, { replace: true }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetProductId])

  // Default to the newest conversation once loaded.
  useEffect(() => {
    if (!activeId && conversations && conversations.length > 0) {
      setActiveConversation(conversations[0].id)
    }
  }, [activeId, conversations, setActiveConversation])

  const { data: conversation, isPending: loadingConversation } = useConversation(activeId)
  const { send, cancel, isStreaming } = useChatStream(activeId)

  // Consume the queued deep-link question once a conversation is live.
  useEffect(() => {
    if (queuedQuestion && activeId && !isStreaming && !error) {
      setQueuedQuestion(null)
      send(queuedQuestion)
    }
  }, [queuedQuestion, activeId, isStreaming, error, send, setQueuedQuestion])

  // Smart auto-scroll: stick to the bottom while streaming, but never fight
  // a user who scrolled up to read; offer a jump-to-latest button instead.
  const viewportRef = useRef<HTMLDivElement>(null)
  const atBottomRef = useRef(true)
  const [showJump, setShowJump] = useState(false)
  const messages = useMemo(() => conversation?.messages ?? [], [conversation])

  const handleScroll = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    atBottomRef.current = distance < 120
    setShowJump(distance > 200)
  }, [])

  useEffect(() => {
    const el = viewportRef.current
    if (el && atBottomRef.current) el.scrollTo({ top: el.scrollHeight })
  }, [messages.length, isStreaming])

  useEffect(() => {
    atBottomRef.current = true
    const el = viewportRef.current
    if (el) requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight }))
  }, [activeId])

  const jumpToLatest = () => {
    const el = viewportRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    atBottomRef.current = true
    setShowJump(false)
  }

  // Escalate this chat: AI-triage the latest customer question into a ticket.
  const escalateConversation = async (messageId?: string) => {
    if (!activeId) return
    try {
      const ticket = await createTicket.mutateAsync({
        conversation_id: activeId,
        message_id: messageId,
      })
      toast.success('Ticket created from this chat', {
        description: `${ticket.category.replace(/_/g, ' ')} · ${ticket.urgency} urgency${ticket.needs_human ? ' · needs human' : ''}`,
        action: { label: 'View queue', onClick: () => navigate('/tickets') },
      })
    } catch (err) {
      toast.error('Could not create ticket', { description: (err as Error).message })
    }
  }

  const conversationProduct = useMemo(
    () => products?.find((p) => p.id === conversation?.product_id) ?? null,
    [products, conversation],
  )

  const startWithProduct = async (productId: string) => {
    try {
      const conversation = await createConversation.mutateAsync(productId)
      setActiveConversation(conversation.id)
      setPickerOpen(false)
    } catch (err) {
      toast.error('Could not start conversation', { description: (err as Error).message })
    }
  }

  return (
    <div className="flex h-full">
      {/* Left rail (desktop) */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-border bg-card/40 lg:flex">
        <ConversationList conversations={conversations ?? []} onStarted={() => setPickerOpen(true)} />
      </aside>

      {/* Chat column */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border bg-card/40 px-4 py-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            {/* Mobile conversation drawer */}
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="shrink-0 lg:hidden" aria-label="Open conversations">
                  <MessagesSquare className="size-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 gap-0 p-0">
                <SheetHeader className="border-b border-border px-4 py-3">
                  <SheetTitle className="text-base">Conversations</SheetTitle>
                  <SheetDescription className="micro-label">your support threads</SheetDescription>
                </SheetHeader>
                <ConversationList
                  conversations={conversations ?? []}
                  onStarted={() => {
                    setDrawerOpen(false)
                    setPickerOpen(true)
                  }}
                  onAfterSelect={() => setDrawerOpen(false)}
                />
              </SheetContent>
            </Sheet>

            <div className="flex size-9 shrink-0 items-center justify-center rounded-sm bg-primary/15 ring-1 ring-primary/30">
              <Bot className="size-5 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-display text-lg leading-tight">
                {conversation?.title ?? conversationProduct?.name ?? 'Support chat'}
              </p>
              <p className="micro-label truncate">
                {conversationProduct
                  ? `${conversationProduct.name} · answering from ${conversationProduct.document_count} manual${conversationProduct.document_count === 1 ? '' : 's'}`
                  : conversation
                    ? 'archived product'
                    : 'pick a product to begin'}
              </p>
            </div>
          </div>

          {/* Active-conversation actions: rename / delete */}
          {conversation && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0"
                  aria-label="Conversation actions"
                >
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuItem onClick={() => void escalateConversation()} disabled={isStreaming}>
                  <TicketIcon className="size-4" /> Create support ticket
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setRenaming(conversation)}>
                  <Pencil className="size-4" /> Rename
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setDeleting(conversation)}
                >
                  <Trash2 className="size-4" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </header>

        <div className="relative min-h-0 flex-1">
          <div ref={viewportRef} onScroll={handleScroll} className="h-full overflow-y-auto">
            <div className="mx-auto max-w-3xl space-y-5 px-4 py-6 md:px-6">
              {loadingConversation && activeId ? (
                <div className="space-y-4">
                  <Skeleton className="h-16 w-2/3" />
                  <Skeleton className="ml-12 h-24 w-3/4" />
                </div>
              ) : !activeId ? (
                <StartConversationPanel
                  products={products ?? []}
                  starting={createConversation.isPending}
                  onStart={(productId) => void startWithProduct(productId)}
                />
              ) : (
                <>
                  {messages.map((message) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      onFollowUp={send}
                      onEscalate={() => void escalateConversation(message.id)}
                    />
                  ))}

                  {/* Optimistic user bubble — visible until the refetched
                      conversation contains the persisted message. */}
                  {pendingUserMessage &&
                    !messages.some((m) => m.role === 'user' && m.content === pendingUserMessage) && (
                      <div className="flex flex-row-reverse gap-3 animate-rise">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-accent ring-1 ring-border">
                          <User className="size-4 text-foreground/80" />
                        </div>
                        <div className="min-w-0 max-w-[85%] text-right">
                          <div className="inline-block max-w-full rounded-md border border-primary/25 bg-primary/10 px-4 py-3 text-left text-sm leading-relaxed">
                            <p className="whitespace-pre-wrap">{pendingUserMessage}</p>
                          </div>
                        </div>
                      </div>
                    )}

                  {isStreaming && <StreamingPanel />}

                  {/* Starter prompts for a fresh conversation */}
                  {!isStreaming && !error && messages.length === 0 && !loadingConversation && (
                    <div className="flex flex-col items-center gap-3 pt-6 text-center animate-rise">
                      <p className="micro-label flex items-center gap-1.5">
                        <Sparkles className="size-3 text-primary/70" /> Try asking
                      </p>
                      <div className="flex flex-wrap justify-center gap-1.5">
                        {STARTER_PROMPTS.map((prompt) => (
                          <button
                            key={prompt}
                            type="button"
                            onClick={() => send(prompt)}
                            className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors outline-none hover:border-primary/40 hover:text-primary focus-visible:ring-2 focus-visible:ring-ring/60"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="flex flex-col items-start gap-2 rounded-sm border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive animate-rise">
                      <span>{error}</span>
                      {lastQuestion && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 gap-1.5 border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => send(lastQuestion)}
                        >
                          <RotateCcw className="size-3.5" /> Retry
                        </Button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {showJump && (
            <Button
              size="icon"
              variant="outline"
              className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full shadow-lg"
              onClick={jumpToLatest}
              aria-label="Jump to latest message"
            >
              <ArrowDown className="size-4" />
            </Button>
          )}
        </div>

        <Composer
          disabled={!activeId || !user}
          isStreaming={isStreaming}
          onSend={send}
          onCancel={cancel}
        />
      </section>

      {/* New-conversation picker */}
      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New conversation</DialogTitle>
            <DialogDescription>Pick the product you need help with.</DialogDescription>
          </DialogHeader>
          <StartConversationPanel
            products={products ?? []}
            starting={createConversation.isPending}
            onStart={(productId) => void startWithProduct(productId)}
            compact
          />
        </DialogContent>
      </Dialog>

      {/* Header rename / delete for the active conversation */}
      {renaming && <RenameConversationDialog conversation={renaming} onClose={() => setRenaming(null)} />}
      {deleting && (
        <DeleteConversationDialog
          conversation={deleting}
          onClose={() => setDeleting(null)}
          onBeforeDelete={() => {
            // Deleting the conversation that is currently streaming — stop first.
            if (isStreaming && deleting.id === activeId) cancel()
          }}
          onDeleted={(deleted) => {
            if (deleted.id === activeId) {
              setActiveConversation(null) // auto-picks the newest remaining one
              toast.info('Switched to your most recent conversation')
            }
          }}
        />
      )}
    </div>
  )
}
