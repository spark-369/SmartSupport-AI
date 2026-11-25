import { BookMarked, FileText } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { SourceRef } from '@/types'

/** SourceRef quote preview with markdown markers stripped for readability. */
function plainText(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[*_~#>|]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function SourceChips({ sources }: { sources: SourceRef[] }) {
  if (sources.length === 0) return null
  return (
    <div className="mt-3 border-t border-border pt-3">
      <p className="micro-label mb-2 flex items-center gap-1.5">
        <BookMarked className="size-3" /> Cited manual excerpts
      </p>
      <div className="flex flex-col gap-1.5">
        {sources.map((source) => (
          <div
            key={source.chunk_id}
            className="group flex items-start gap-2 rounded-xs border border-border/70 bg-muted/50 px-2.5 py-2"
          >
            <FileText className="mt-0.5 size-3.5 shrink-0 text-primary/70" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-mono text-[11px] text-foreground/80">{source.document_name}</span>
                {source.page != null && <Badge variant="outline">p.{source.page}</Badge>}
                <Badge variant="outline" className="ml-auto shrink-0">
                  {Math.round(source.score * 100)}% match
                </Badge>
              </div>
              <p className="mt-1 line-clamp-2 text-xs italic text-muted-foreground">
                “{plainText(source.quote)}”
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
