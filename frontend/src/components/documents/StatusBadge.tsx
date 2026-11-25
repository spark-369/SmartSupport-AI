import { Badge } from '@/components/ui/badge'
import type { DocumentStatus } from '@/types'

const LABELS: Record<DocumentStatus, string> = {
  pending: 'Queued',
  processing: 'Ingesting',
  ready: 'Ready',
  failed: 'Failed',
}

const VARIANTS: Record<DocumentStatus, 'warning' | 'secondary' | 'success' | 'destructive'> = {
  pending: 'warning',
  processing: 'secondary',
  ready: 'success',
  failed: 'destructive',
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge variant={VARIANTS[status]}>
      <span className={status === 'processing' ? 'animate-pulse-soft' : undefined}>{LABELS[status]}</span>
    </Badge>
  )
}
