import * as React from 'react'

import { cn } from '@/lib/utils'

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'flex min-h-16 w-full rounded-sm border border-input bg-muted/60 px-3 py-2 text-sm transition-colors',
        'placeholder:text-muted-foreground/70 focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring/50 outline-none',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { Textarea }
