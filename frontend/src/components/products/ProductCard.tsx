import { Link } from 'react-router-dom'
import { ArrowUpRight, FileText } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { StatusBadge } from '@/components/documents/StatusBadge'
import type { Product } from '@/types'

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const ingesting = product.processing_count + product.pending_count

  return (
    <Link to={`/products/${product.id}`} className="group block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <Card className="scanline h-full p-5 transition-colors group-hover:border-primary/30">
        <div className="flex items-start justify-between gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm bg-accent ring-1 ring-border">
            <FileText className="size-5 text-primary" />
          </div>
          <ArrowUpRight className="size-4 text-muted-foreground transition-colors group-hover:text-primary" />
        </div>

        <h3 className="mt-4 font-display text-xl leading-snug">{product.name}</h3>
        {product.description && (
          <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{product.description}</p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted-foreground">
          <span>
            {product.ready_count} ready · {product.total_chunks} chunks
          </span>
          {ingesting > 0 && <StatusBadge status="processing" />}
          {product.pending_count > 0 && <StatusBadge status="pending" />}
          {product.failed_count > 0 && <StatusBadge status="failed" />}
        </div>
      </Card>
    </Link>
  )
}
