import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { toast } from 'sonner'

import './index.css'
import App from './App.tsx'
import { Toaster } from '@/components/ui/sonner'
import { ApiError } from '@/lib/api'

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    // Global safety net for queries that fail without a local handler.
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 404)) return
      toast.error('Request failed', { description: error.message })
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster />
    </QueryClientProvider>
  </StrictMode>,
)
