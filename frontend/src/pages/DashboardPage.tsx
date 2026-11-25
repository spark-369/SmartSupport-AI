import { useMemo, useState, type ReactNode } from 'react'
import { BookOpen, Plus, Search, ShieldQuestion, TriangleAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ProductCard } from '@/components/products/ProductCard'
import { ProductFormDialog } from '@/components/products/ProductFormDialog'
import { useProducts } from '@/hooks/queries'
import { useAuthStore } from '@/stores/authStore'

export default function DashboardPage() {
  const { data: products, isPending } = useProducts()
  const user = useAuthStore((s) => s.user)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [query, setQuery] = useState('')
  const isAdmin = user?.role === 'admin'

  const stats = useMemo(() => {
    const list = products ?? []
    return {
      products: list.length,
      manuals: list.reduce((sum, p) => sum + p.document_count, 0),
      chunks: list.reduce((sum, p) => sum + p.total_chunks, 0),
      attention:
        list.reduce((sum, p) => sum + p.failed_count, 0) +
        list.reduce((sum, p) => sum + p.pending_count, 0) +
        list.reduce((sum, p) => sum + p.processing_count, 0),
    }
  }, [products])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products ?? []
    return (products ?? []).filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q) ||
        (p.description ?? '').toLowerCase().includes(q),
    )
  }, [products, query])

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-border bg-card/40 px-6 py-6 backdrop-blur md:px-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-4">
          <div>
            <p className="micro-label">Field manual library</p>
            <h1 className="mt-1 font-display text-3xl">
              Product <span className="italic text-primary">knowledge</span>
            </h1>
          </div>
          {isAdmin && (
            <Button onClick={() => setDialogOpen(true)}>
              <Plus className="size-4" /> New product
            </Button>
          )}
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8 md:px-8">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Products" value={stats.products} icon={<BookOpen className="size-4 text-primary" />} />
          <StatCard label="Manuals" value={stats.manuals} />
          <StatCard label="Indexed chunks" value={stats.chunks} mono />
          <StatCard
            label="Needs attention"
            value={stats.attention}
            icon={<TriangleAlert className="size-4 text-warning" />}
            alert={stats.attention > 0}
          />
        </div>

        {(products?.length ?? 0) > 3 && (
          <div className="relative mt-6 max-w-sm">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search products…"
              className="pl-9"
              aria-label="Search products"
            />
          </div>
        )}

        <div className="mt-6">
          {isPending ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-44" />
              ))}
            </div>
          ) : (products?.length ?? 0) === 0 ? (
            <EmptyState isAdmin={isAdmin} onStart={() => setDialogOpen(true)} />
          ) : filtered.length === 0 ? (
            <div className="mt-4 rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
              No products match “{query}”.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>

      <ProductFormDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}

function EmptyState({ isAdmin, onStart }: { isAdmin: boolean; onStart: () => void }) {
  return (
    <div className="mt-4 rounded-md border border-dashed border-border p-14 text-center">
      {isAdmin ? (
        <>
          <BookOpen className="mx-auto size-9 text-muted-foreground" />
          <p className="mt-4 font-display text-2xl">Start your first product</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            Register a product, upload its manuals, and the support bot will answer
            strictly from those documents — with citations.
          </p>
          <Button className="mt-5" onClick={onStart}>
            <Plus className="size-4" /> New product
          </Button>
        </>
      ) : (
        <>
          <ShieldQuestion className="mx-auto size-9 text-muted-foreground" />
          <p className="mt-4 font-display text-2xl">Waiting on content</p>
          <p className="mt-2 text-sm text-muted-foreground">
            No products yet. An admin can register products and upload manuals.
          </p>
        </>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  mono = false,
  alert = false,
}: {
  label: string
  value: number
  icon?: ReactNode
  mono?: boolean
  alert?: boolean
}) {
  return (
    <div
      className={
        'rounded-md border p-4 transition-colors ' +
        (alert ? 'border-warning/30 bg-warning/5' : 'border-border bg-card/50')
      }
    >
      <div className="flex items-center justify-between gap-2">
        <span className="micro-label">{label}</span>
        {icon}
      </div>
      <p className={`mt-2 text-2xl ${mono ? 'font-mono' : 'font-display'}`}>
        {value.toLocaleString()}
      </p>
    </div>
  )
}
