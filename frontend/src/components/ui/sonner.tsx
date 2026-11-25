import { Toaster as Sonner } from 'sonner'

function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="top-right"
      toastOptions={{
        classNames: {
          toast:
            '!bg-popover !border !border-border !text-foreground !rounded-md !font-sans !shadow-xl',
          description: '!text-muted-foreground',
          actionButton: '!bg-primary !text-primary-foreground',
        },
      }}
    />
  )
}

export { Toaster }
