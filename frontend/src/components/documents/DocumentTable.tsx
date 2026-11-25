import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileDown, FileUp, Loader2, RotateCcw, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/documents/StatusBadge'
import { downloadFile } from '@/lib/api'
import { formatBytes, formatDate } from '@/lib/utils'
import { useDeleteDocument, useRetryDocument } from '@/hooks/queries'
import type { Document } from '@/types'

interface DocumentTableProps {
  productId: string
  documents: Document[]
  canManage: boolean
}

export function DocumentTable({ productId, documents, canManage }: DocumentTableProps) {
  const deleteDocument = useDeleteDocument(productId)
  const retryDocument = useRetryDocument(productId)
  const [busyId, setBusyId] = useState<string | null>(null)

  const onDownload = async (document: Document) => {
    setBusyId(document.id)
    try {
      await downloadFile(`/documents/${document.id}/file`, document.original_filename)
    } catch (error) {
      toast.error('Download failed', { description: (error as Error).message })
    } finally {
      setBusyId(null)
    }
  }

  const onDelete = async (document: Document) => {
    setBusyId(document.id)
    try {
      await deleteDocument.mutateAsync(document.id)
      toast.success('Document deleted', { description: document.original_filename })
    } catch (error) {
      toast.error('Delete failed', { description: (error as Error).message })
    } finally {
      setBusyId(null)
    }
  }

  const onRetry = async (document: Document) => {
    setBusyId(document.id)
    try {
      await retryDocument.mutateAsync(document.id)
      toast.info('Re-ingesting document', { description: document.original_filename })
    } catch (error) {
      toast.error('Retry failed', { description: (error as Error).message })
    } finally {
      setBusyId(null)
    }
  }

  if (documents.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-10 text-center">
        <FileUp className="mx-auto size-8 text-muted-foreground" />
        <p className="mt-3 font-display text-lg">No manuals yet</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {canManage ? 'Upload a PDF, Markdown, TXT or DOCX manual to enable answers.' : 'Ask an admin to upload the manuals.'}
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left">
            <th className="micro-label px-4 py-3">Manual</th>
            <th className="micro-label px-4 py-3">Status</th>
            <th className="micro-label px-4 py-3">Chunks</th>
            <th className="micro-label px-4 py-3">Size</th>
            <th className="micro-label px-4 py-3">Uploaded</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id} className="border-b border-border/60 last:border-0 hover:bg-accent/40">
              <td className="max-w-64 truncate px-4 py-3">
                <span className="inline-flex items-center gap-2">
                  <FileDown className="size-4 shrink-0 text-primary/70" />
                  <span className="truncate">{document.original_filename}</span>
                </span>
                {document.error && <p className="mt-1 line-clamp-2 text-xs text-destructive">{document.error}</p>}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={document.status} />
              </td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{document.chunk_count || '—'}</td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{formatBytes(document.size_bytes)}</td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{formatDate(document.created_at)}</td>
              <td className="px-4 py-3">
                {canManage && (
                  <div className="flex justify-end gap-1">
                    {document.status === 'failed' && (
                      <Button variant="ghost" size="icon" title="Retry ingestion" onClick={() => void onRetry(document)} disabled={busyId === document.id}>
                        <RotateCcw className="size-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Download original"
                      onClick={() => void onDownload(document)}
                      disabled={busyId === document.id}
                    >
                      {busyId === document.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <FileDown className="size-4" />
                      )}
                    </Button>
                    <Button variant="ghost" size="icon" title="Delete" onClick={() => void onDelete(document)} disabled={busyId === document.id}>
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ProductHint({ productId }: { productId: string }) {
  return (
    <Link to={`/chat?product=${productId}`} className="text-xs text-primary underline-offset-4 hover:underline">
      Open support chat →
    </Link>
  )
}
