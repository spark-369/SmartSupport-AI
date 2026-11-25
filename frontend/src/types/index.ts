/** API contract types mirroring backend Pydantic schemas. */

export type UserRole = 'admin' | 'user'
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'
export type MessageRole = 'user' | 'assistant'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  token_type: string
  expires_in: number
}

export interface Product {
  id: string
  name: string
  slug: string
  description: string | null
  version: string | null
  is_active: boolean
  document_count: number
  pending_count: number
  processing_count: number
  ready_count: number
  failed_count: number
  total_chunks: number
  created_at: string
}

export interface Document {
  id: string
  product_id: string
  original_filename: string
  file_type: string
  size_bytes: number
  status: DocumentStatus
  error: string | null
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface SourceRef {
  chunk_id: string
  document_name: string
  quote: string
  score: number
  page: number | null
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  sources: SourceRef[]
  follow_ups: string[]
  confidence: number | null
  found_in_manual: boolean | null
  latency_ms: number | null
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  product_id: string | null
  product_name: string | null
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface AnalyticsTotals {
  conversations: number
  user_questions: number
  assistant_answers: number
  active_users: number
  avg_confidence: number | null
  grounded_rate: number | null
  avg_latency_ms: number | null
}

export interface ProductAnalytics {
  product_id: string
  product_name: string
  conversations: number
  questions: number
  avg_confidence: number | null
  unanswered: number
}

export interface KnowledgeGap {
  conversation_id: string
  product_name: string | null
  question: string
  answer_preview: string
  confidence: number | null
  created_at: string
}

export interface TopQuestion {
  question: string
  count: number
}

export interface AnalyticsOverview {
  totals: AnalyticsTotals
  per_product: ProductAnalytics[]
  knowledge_gaps: KnowledgeGap[]
  top_questions: TopQuestion[]
}

export interface SearchResultItem {
  chunk_id: string
  product_id: string
  product_name: string
  document_name: string
  content: string
  score: number
  page: number | null
}

export interface SearchResponse {
  query: string
  total: number
  results: SearchResultItem[]
}

export type TicketStatus = 'open' | 'escalated' | 'resolved' | 'dismissed'
export type TicketUrgency = 'low' | 'medium' | 'high' | 'critical'

export type TicketCounts = Record<string, number>
export type TicketSentiment = 'satisfied' | 'neutral' | 'concerned' | 'frustrated' | 'angry'

export interface TicketExtractedData {
  product: string | null
  issue: string | null
  requested_action: string | null
  topics: string[]
}

export interface Ticket {
  id: string
  status: TicketStatus
  raw_message: string
  product_id: string | null
  product_name: string | null
  conversation_id: string | null
  source_message_id: string | null
  created_by: string | null
  created_by_name: string | null
  category: string
  urgency: TicketUrgency
  sentiment: TicketSentiment
  needs_human: boolean
  escalation_reason: string | null
  summary: string
  suggested_reply: string | null
  extracted_data: TicketExtractedData
  triage_latency_ms: number | null
  resolution_note: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

/** SSE events emitted by the streaming chat endpoint. */
export type ChatStage = 'understanding_question' | 'searching_manual' | 'generating_answer'

export interface ChatErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
