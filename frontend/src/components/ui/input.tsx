import * as React from 'react'

import { cn } from '@/lib/utils'

function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'flex h-9 w-full min-w-0 rounded-sm border border-input bg-muted/60 px-3 py-1 text-sm transition-colors',
        'placeholder:text-muted-foreground/70 selection:bg-primary selection:text-primary-foreground',
        'focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring/50 outline-none',
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
