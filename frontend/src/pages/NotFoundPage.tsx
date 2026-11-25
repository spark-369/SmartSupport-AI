import { Link } from 'react-router-dom'
import { ArrowLeft, Compass } from 'lucide-react'

import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 p-8 text-center">
      <div className="flex size-14 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/30">
        <Compass className="size-7 text-primary" />
      </div>
      <div>
        <p className="font-mono text-[11px] tracking-[0.3em] text-muted-foreground uppercase">Error 404</p>
        <h1 className="mt-2 font-display text-4xl">
          Page <span className="italic text-primary">not found</span>
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          The page you are looking for was moved, removed or never existed.
        </p>
      </div>
      <Button asChild>
        <Link to="/">
          <ArrowLeft className="size-4" /> Back to products
        </Link>
      </Button>
    </div>
  )
}