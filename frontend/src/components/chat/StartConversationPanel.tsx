import { Bot, BookOpen, Loader2, MessageSquarePlus } from 'lucide-react'

import type { Product } from '@/types'

interface StartConversationPanelProps {
  products: Product[]
  starting: boolean
  onStart: (productId: string) => void
  compact?: boolean
}

/** Product picker — used as the chat empty state and inside the "New" dialog. */
export function StartConversationPanel({ products, starting, onStart, compact = false }: StartConversationPanelProps) {
  return (
    <div className={compact ? 'space-y-2' : 'flex h-full min-h-72 flex-col items-center justify-center py-8 text-center'}>
      {!compact && (
        <div className="mb-2">
          <div className="mx-auto flex size-12 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/30">
            <Bot className="size-6 text-primary" />
          </div>
          <p className="mt-4 font-display text-2xl">Your manual, answered.</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            Pick a product to start — every answer is retrieved from its manuals
            and cited to the exact excerpt.
          </p>
        </div>
      )}

      {products.length === 0 ? (
        <div className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">
          No products registered yet. An admin can add products and upload manuals
          on the <span className="text-primary">Products</span> page.
        </div>
      ) : (
        <div
          className={
            compact
              ? 'grid max-h-80 gap-2 overflow-y-auto pr-1'
              : 'mt-6 grid w-full max-w-xl gap-2 sm:grid-cols-2'
          }
        >
          {products.map((product) => (
            <button
              key={product.id}
              type="button"
              disabled={starting}
              onClick={() => onStart(product.id)}
              className="group flex items-center gap-3 rounded-sm border border-border bg-card px-4 py-3 text-left transition-colors hover:border-primary/40 hover:bg-accent disabled:pointer-events-none disabled:opacity-60 outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              <BookOpen className="size-4 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{product.name}</span>
                <span className="micro-label block truncate">
                  {product.document_count} manual{product.document_count === 1 ? '' : 's'}
                  {product.version ? ` · v${product.version}` : ''}
                </span>
              </span>
              {starting ? (
                <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
              ) : (
                <MessageSquarePlus className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
