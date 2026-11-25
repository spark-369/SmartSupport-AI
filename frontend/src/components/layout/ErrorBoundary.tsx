import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

/** Catches render-time crashes and shows a recoverable full-screen state. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error('Unhandled UI error:', error)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
          <div className="flex size-12 items-center justify-center rounded-md bg-destructive/15 ring-1 ring-destructive/30">
            <AlertTriangle className="size-6 text-destructive" />
          </div>
          <div>
            <p className="font-display text-2xl">Something went wrong</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              {this.state.error.message || 'An unexpected error occurred while rendering this view.'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => this.setState({ error: null })}>
              <RotateCcw className="size-4" /> Try again
            </Button>
            <Button variant="ghost" onClick={() => window.location.assign('/')}>
              Go home
            </Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}