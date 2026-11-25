/** Shared conversation rename / delete dialogs (sidebar rows + chat header). */

import { useState } from 'react'
import { toast } from 'sonner'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useDeleteConversation, useRenameConversation } from '@/hooks/queries'
import type { Conversation } from '@/types'

interface RenameConversationDialogProps {
  conversation: Conversation
  onClose: () => void
}

/** Render only while a conversation is selected — state re-seeds per mount. */
export function RenameConversationDialog({ conversation, onClose }: RenameConversationDialogProps) {
  const renameConversation = useRenameConversation()
  const [title, setTitle] = useState(conversation.title)

  const submit = async () => {
    const next = title.trim()
    if (!next || next === conversation.title) {
      onClose()
      return
    }
    try {
      await renameConversation.mutateAsync({ id: conversation.id, title: next })
      toast.success('Conversation renamed')
      onClose()
    } catch (error) {
      toast.error('Rename failed', { description: (error as Error).message })
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Rename conversation</DialogTitle>
          <DialogDescription>Pick a title you will recognize later.</DialogDescription>
        </DialogHeader>
        <Input
          value={title}
          maxLength={200}
          autoFocus
          onChange={(event) => setTitle(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              void submit()
            }
          }}
          aria-label="Conversation title"
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={!title.trim() || renameConversation.isPending}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface DeleteConversationDialogProps {
  conversation: Conversation
  onClose: () => void
  /** Invoked before the DELETE request (e.g. abort an in-flight stream). */
  onBeforeDelete?: () => void
  /** Invoked after successful deletion (e.g. clear the active selection). */
  onDeleted?: (conversation: Conversation) => void
}

export function DeleteConversationDialog({
  conversation,
  onClose,
  onBeforeDelete,
  onDeleted,
}: DeleteConversationDialogProps) {
  const deleteConversation = useDeleteConversation()

  const submit = async () => {
    onBeforeDelete?.()
    try {
      await deleteConversation.mutateAsync(conversation.id)
      toast.success('Conversation deleted')
      onDeleted?.(conversation)
    } catch (error) {
      toast.error('Delete failed', { description: (error as Error).message })
    } finally {
      onClose()
    }
  }

  return (
    <AlertDialog open onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
          <AlertDialogDescription>
            “{conversation.title}” and all of its messages will be permanently removed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={() => void submit()}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}