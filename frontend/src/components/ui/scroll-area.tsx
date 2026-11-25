import * as React from 'react'
import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area'

import { cn } from '@/lib/utils'

function ScrollArea({ className, children, viewportRef, ...props }: React.ComponentProps<typeof ScrollAreaPrimitive.Root> & { viewportRef?: React.Ref<HTMLDivElement> }) {
  return (
    <ScrollAreaPrimitive.Root data-slot="scroll-area" className={cn('relative overflow-hidden', className)} {...props}>
      <ScrollAreaPrimitive.Viewport ref={viewportRef} className="size-full rounded-[inherit] outline-none">
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollAreaPrimitive.Scrollbar
        orientation="vertical"
        className="flex w-2 touch-none p-px transition-colors select-none"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-border" />
      </ScrollAreaPrimitive.Scrollbar>
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
}

export { ScrollArea }
