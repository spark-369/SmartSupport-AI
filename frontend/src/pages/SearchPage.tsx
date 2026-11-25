import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, MessageSquarePlus, Search, SearchX, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useProducts, useSearch } from '@/hooks/queries'
import type { SearchResultItem } from '@/types'

export default function SearchPage() {
  const navigate = useNavigate()
  const { data: products } = useProducts()
  const search = useSearch()

  const [query, setQuery] = useState('')
  const [productId, setProductId] = useState('')
  const [lastQuery, setLastQuery] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const q = query.trim()
    if (q.length < 2) return
    setLastQuery(q)
    search.mutate({ query: q, product_id: productId || undefined })
  }

  const askInChat = (result: SearchResultItem) => {
    navigate(`/chat?product=${result.product_id}&q=${encodeURIComponent(lastQuery)}`)
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-border bg-card/40 px-6 py-6 backdrop-blur md:px-8">
        <div className="mx-auto max-w-4xl">
          <p className="micro-label flex items-center gap-1.5">
            <Sparkles className="size-3 text-primary" /> Semantic · embeddings · cosine
          </p>
          <h1 className="mt-1 font-display text-3xl">
            Manual <span className="italic text-primary">search</span>
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Search every manual by meaning — the same retrieval engine the chat bot uses.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8 md:px-8">
        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search manuals — e.g. “descale”, “error codes”, “warranty”…"
              className="pl-9"
              aria-label="Search manuals"
            />
          </div>
          <select
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
            aria-label="Filter by product"
            className="h-9 rounded-sm border border-border bg-card px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <option value="">All products</option>
            {(products ?? []).map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={query.trim().length < 2 || search.isPending}>
            {search.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            Search
          </Button>
        </form>

        <div className="mt-6">
          {search.isPending ? (
            <div className="space-y-3">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          ) : search.data ? (
            search.data.total === 0 ? (
              <EmptyState query={lastQuery} />
            ) : (
              <div className="space-y-3">
                <p className="micro-label">
                  {search.data.total} result{search.data.total === 1 ? '' : 's'} for “{lastQuery}”
                </p>
                {search.data.results.map((result) => (
                  <ResultCard
                    key={result.chunk_id}
                    result={result}
                    query={lastQuery}
                    onAsk={() => askInChat(result)}
                  />
                ))}
              </div>
            )
          ) : (
            <p className="rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
              Enter a query to search the ingested manuals.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
function ResultCard({
  result,
  query,
  onAsk,
}: {
  result: SearchResultItem
  query: string
  onAsk: () => void
}) {
  return (
    <Card className="scanline">
      <CardContent className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-foreground/85">{result.document_name}</span>
          {result.page != null && <Badge variant="outline">p.{result.page}</Badge>}
          <Badge variant="outline" className="text-primary">
            {Math.round(result.score * 100)}% match
          </Badge>
          <span className="micro-label truncate">{result.product_name}</span>
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={onAsk}>
              <MessageSquarePlus className="size-3.5" /> Ask in chat
            </Button>
          </div>
        </div>
        <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
          <Highlighted text={result.content} query={query} />
        </p>
      </CardContent>
    </Card>
  )
}

function Highlighted({ text, query }: { text: string; query: string }) {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((term) => term.length > 2)
  if (terms.length === 0) return <>{text}</>
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi')
  const parts = text.split(pattern)
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <mark key={index} className="rounded-xs bg-primary/25 px-0.5 text-foreground">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  )
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function EmptyState({ query }: { query: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-12 text-center">
      <SearchX className="mx-auto size-8 text-muted-foreground" />
      <p className="mt-3 font-display text-lg">No matches for “{query}”</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Nothing in the ingested manuals matches yet. An admin can upload more
        documentation on the product page.
      </p>
    </div>
  )
}
