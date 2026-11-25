import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { productSchema, type ProductValues } from '@/lib/validation'
import { useCreateProduct, useUpdateProduct } from '@/hooks/queries'
import type { Product } from '@/types'

interface ProductFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** When provided the dialog edits this product instead of creating one. */
  product?: Product | null
}

export function ProductFormDialog({ open, onOpenChange, product }: ProductFormDialogProps) {
  const createProduct = useCreateProduct()
  const updateProduct = useUpdateProduct(product?.id ?? '')
  const editing = Boolean(product)

  const form = useForm<ProductValues>({
    resolver: zodResolver(productSchema),
    defaultValues: { name: '', slug: '', description: '', version: '' },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        name: product?.name ?? '',
        slug: product?.slug ?? '',
        description: product?.description ?? '',
        version: product?.version ?? '',
      })
    }
  }, [open, product, form])

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      if (product) {
        await updateProduct.mutateAsync(values)
        toast.success('Product updated', { description: values.name })
      } else {
        await createProduct.mutateAsync(values)
        toast.success('Product created', { description: values.name })
      }
      onOpenChange(false)
    } catch (error) {
      toast.error(product ? 'Could not update product' : 'Could not create product', {
        description: (error as Error).message,
      })
    }
  })

  const pending = createProduct.isPending || updateProduct.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit product' : 'New product'}</DialogTitle>
          <DialogDescription>
            {editing
              ? 'Update the catalog entry. Conversations keep their snapshot name history.'
              : 'Register a product to attach its manuals.'}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={onSubmit} className="grid gap-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Aurora Coffee Maker X100" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="version"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Version</FormLabel>
                    <FormControl>
                      <Input placeholder="2.1" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="slug"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Slug (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="aurora-x100" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea rows={3} placeholder="18-bar espresso machine…" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={pending}>
                {pending ? (editing ? 'Saving…' : 'Creating…') : editing ? 'Save changes' : 'Create product'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
