/** TanStack Query hooks for every REST surface. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, setAccessToken } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type {
  AnalyticsOverview,
  Conversation,
  ConversationDetail,
  Document,
  Product,
  SearchResponse,
  Ticket,
  TicketCounts,
  TokenPair,
  User,
} from '@/types'

export const queryKeys = {
  products: ['products'] as const,
  product: (id: string) => ['products', id] as const,
  documents: (productId: string) => ['documents', productId] as const,
  conversations: ['conversations'] as const,
  conversation: (id: string) => ['conversations', id] as const,
}

// --- products ------------------------------------------------------------

export function useProducts() {
  return useQuery({
    queryKey: queryKeys.products,
    queryFn: () => api.get<Product[]>('/products'),
  })
}

export function useCreateProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; slug?: string; description?: string; version?: string }) =>
      api.post<Product>('/products', body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.products }),
  })
}

export function useUpdateProduct(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<{ name: string; description: string; version: string; is_active: boolean }>) =>
      api.patch<Product>(`/products/${productId}`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.products }),
  })
}

export function useDeleteProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (productId: string) => api.delete<void>(`/products/${productId}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.products }),
  })
}

// --- documents -----------------------------------------------------------

export function useDocuments(productId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.documents(productId ?? ''),
    enabled: Boolean(productId),
    queryFn: () => api.get<Document[]>(`/products/${productId}/documents`),
    // Ingestion is async — poll while anything is still moving.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === 'pending' || d.status === 'processing')
        ? 2000
        : false,
  })
}

export function useUploadDocument(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.upload<Document>(`/products/${productId}/documents`, form)
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.documents(productId) }),
  })
}

export function useDeleteDocument(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => api.delete<void>(`/documents/${documentId}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.documents(productId) }),
  })
}

export function useRetryDocument(productId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => api.post<Document>(`/documents/${documentId}/retry`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.documents(productId) }),
  })
}

// --- conversations -------------------------------------------------------

export function useConversations() {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => api.get<Conversation[]>('/conversations'),
  })
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: queryKeys.conversation(id ?? ''),
    enabled: Boolean(id),
    queryFn: () => api.get<ConversationDetail>(`/conversations/${id}`),
  })
}

export function useCreateConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (productId: string) => api.post<Conversation>('/conversations', { product_id: productId }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.conversations }),
  })
}

export function useDeleteConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/conversations/${id}`),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: queryKeys.conversation(id) })
      void qc.invalidateQueries({ queryKey: queryKeys.conversations })
    },
  })
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => api.get<User>('/auth/me'),
    staleTime: 60_000,
  })
}

export function useProduct(productId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.product(productId ?? ''),
    enabled: Boolean(productId),
    queryFn: () => api.get<Product>(`/products/${productId}`),
  })
}

// --- profile --------------------------------------------------------------

export function useUpdateMe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { full_name: string }) => api.patch<User>('/auth/me', body),
    onSuccess: (user) => {
      useAuthStore.getState().setUser(user)
      void qc.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.post<TokenPair>('/auth/password', body),
    onSuccess: (pair) => {
      // The backend rotated every refresh session and re-issued this device's
      // pair — keep the in-memory + persisted access token in sync.
      setAccessToken(pair.access_token)
      useAuthStore.setState({ accessToken: pair.access_token })
    },
  })
}

// --- conversations ----------------------------------------------------------

export function useRenameConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch<Conversation>(`/conversations/${id}`, { title }),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: queryKeys.conversations })
      void qc.invalidateQueries({ queryKey: queryKeys.conversation(vars.id) })
    },
  })
}

// --- insights & search ------------------------------------------------------

export function useAnalyticsOverview(enabled: boolean) {
  return useQuery({
    queryKey: ['analytics'],
    queryFn: () => api.get<AnalyticsOverview>('/analytics/overview'),
    enabled,
    staleTime: 30_000,
  })
}

export function useSearch() {
  return useMutation({
    mutationFn: (body: { query: string; product_id?: string }) =>
      api.post<SearchResponse>('/search', body),
  })
}

// --- ticket triage ----------------------------------------------------------

export function useTickets(
  filters: { status?: string; needs_human?: boolean; urgency?: string; search?: string },
  options?: { refetchInterval?: number },
) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.needs_human !== undefined) params.set('needs_human', String(filters.needs_human))
  if (filters.urgency) params.set('urgency', filters.urgency)
  if (filters.search) params.set('search', filters.search)
  const qs = params.toString()
  return useQuery({
    queryKey: [
      'tickets',
      filters.status ?? 'all',
      filters.needs_human ?? 'any',
      filters.urgency ?? 'any',
      filters.search ?? '',
    ],
    queryFn: () => api.get<Ticket[]>(`/tickets${qs ? `?${qs}` : ''}`),
    refetchInterval: options?.refetchInterval ?? false,
  })
}

export function useTicketCounts() {
  return useQuery({
    queryKey: ['ticket-counts'],
    queryFn: () => api.get<TicketCounts>('/tickets/counts'),
    refetchInterval: 20_000,
  })
}

export function useCreateTicketFromConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { conversation_id: string; message_id?: string }) =>
      api.post<Ticket>(`/conversations/${body.conversation_id}/tickets`, {
        message_id: body.message_id,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tickets'] })
      void qc.invalidateQueries({ queryKey: ['ticket-counts'] })
    },
  })
}

export function useUpdateTicketStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, resolution_note }: { id: string; status: string; resolution_note?: string }) =>
      api.patch<Ticket>(`/tickets/${id}`, { status, resolution_note }),
    onSuccess: (ticket) => {
      void qc.invalidateQueries({ queryKey: ['tickets'] })
      void qc.invalidateQueries({ queryKey: ['ticket-counts'] })
      void qc.invalidateQueries({ queryKey: ['ticket', ticket.id] })
    },
  })
}
