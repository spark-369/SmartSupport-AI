import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, MessageSquare, Pencil, Trash2, Upload, UploadCloud } from 'lucide-react'
import { toast } from 'sonner'

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { DocumentTable } from '@/components/documents/DocumentTable'
import { ProductFormDialog } from '@/components/products/ProductFormDialog'
import { useDeleteProduct, useDocuments, useProduct, useUploadDocument } from '@/hooks/queries'
import { useAuthStore } from '@/stores/authStore'

const MAX_MB = 20

export default function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [editOpen, setEditOpen] = useState(false)

  const { data: product, isPending: productLoading } = useProduct(productId)
  const { data: documents, isPending } = useDocuments(productId)
  const uploadDocument = useUploadDocument(productId!)
  const deleteProduct = useDeleteProduct()

  const handleFile = async (file: File) => {
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error('File too large', { description: `Maximum ${MAX_MB} MB.` })
      return
    }
    try {
      await uploadDocument.mutateAsync(file)
      toast.info('Ingestion queued', { description: `${file.name} — chunking & embedding started.` })
    } catch (error) {
      toast.error('Upload failed', { description: (error as Error).message })
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="sticky top-0 z-10 border-b border-border bg-background/90 px-6 py-5 backdrop-blur md:px-8">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div className="min-w-0">
            <Button variant="ghost" size="sm" className="mb-1 -ml-2 gap-1.5 text-muted-foreground" onClick={() => navigate('/')}>
              <ArrowLeft className="size-3.5" /> All products
            </Button>
            {productLoading ? (
              <Skeleton className="h-7 w-56" />
            ) : (
              <h1 className="truncate font-display text-2xl">{product?.name ?? 'Product'}</h1>
            )}
            <p className="micro-label mt-0.5 truncate">
              {product
                ? [
                    `product/${product.slug}`,
                    product.version ? `v${product.version}` : null,
                    product.is_active ? null : 'inactive',
                  ]
                    .filter(Boolean)
                    .join(' · ')
                : 'loading…'}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <Button variant="outline" asChild>
              <Link to={`/chat?product=${productId}`}>
                <MessageSquare className="size-4" /> Support chat
              </Link>
            </Button>
            {isAdmin && (
              <>
                <Button variant="outline" onClick={() => setEditOpen(true)}>
                  <Pencil className="size-4" /> Edit
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" className="text-destructive hover:text-destructive">
                      <Trash2 className="size-4" /> Delete
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete this product?</AlertDialogTitle>
                      <AlertDialogDescription>
                        All manuals, embeddings and queued ingestion jobs for this product will be removed.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => void deleteProduct.mutateAsync(productId!).then(() => navigate('/'))}
                      >
                        Delete product
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-5xl flex-1 px-6 py-6 md:px-8">
        {product?.description && (
          <p className="mb-4 max-w-2xl text-sm text-muted-foreground">{product.description}</p>
        )}
        {isAdmin && (
          <div
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              const file = event.dataTransfer.files?.[0]
              if (file) void handleFile(file)
            }}
            onClick={() => fileInputRef.current?.click()}
            className={[
              'cursor-pointer rounded-md border-2 border-dashed p-8 text-center transition-colors',
              dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40 hover:bg-accent/40',
            ].join(' ')}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.md,.markdown,.txt,.docx"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleFile(file)
                event.target.value = ''
              }}
            />
            <UploadCloud
              className={`mx-auto size-9 ${uploadDocument.isPending ? 'animate-pulse text-primary' : 'text-muted-foreground'}`}
            />
            <p className="mt-3 font-display text-lg">
              {uploadDocument.isPending ? 'Uploading…' : 'Drop a manual here'}
            </p>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              PDF · Markdown · TXT · DOCX — max {MAX_MB} MB
            </p>
          </div>
        )}

        <div className="mt-6">
          {isPending ? (
            <Skeleton className="h-40" />
          ) : (
            <DocumentTable productId={productId!} documents={documents ?? []} canManage={isAdmin} />
          )}
        </div>

        <p className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
          <Upload className="mt-0.5 size-3.5 shrink-0" />
          Celery workers extract, chunk and embed each document locally (Qwen3-Embedding-0.6B).
          The chat answers only from ingested chunks.
        </p>
      </div>

      <ProductFormDialog open={editOpen} onOpenChange={setEditOpen} product={product ?? null} />
    </div>
  )
}
