/** Live streaming state for the chat surface (Zustand). */

import { create } from 'zustand'

import type { ChatStage, Message, SourceRef } from '@/types'

interface ChatState {
  activeConversationId: string | null
  pendingUserMessage: string | null
  stage: ChatStage | null
  streamingSources: SourceRef[]
  streamedContent: string | null
  streamedMessage: Message | null
  lastQuestion: string | null
  queuedQuestion: string | null
  error: string | null
  isStreaming: boolean

  setActiveConversation: (id: string | null) => void
  beginStream: (question: string) => void
  setStage: (stage: ChatStage) => void
  setSources: (sources: SourceRef[]) => void
  appendToken: (delta: string) => void
  setStreamedMessage: (message: Message) => void
  fail: (message: string) => void
  endStream: () => void
  abortStream: () => void
  setQueuedQuestion: (question: string | null) => void
}

export const useChatStore = create<ChatState>((set) => ({
  activeConversationId: null,
  pendingUserMessage: null,
  stage: null,
  streamingSources: [],
  streamedContent: null,
  streamedMessage: null,
  lastQuestion: null,
  queuedQuestion: null,
  error: null,
  isStreaming: false,

  setActiveConversation: (id) =>
    set({
      activeConversationId: id,
      pendingUserMessage: null,
      stage: null,
      streamingSources: [],
      streamedContent: null,
      streamedMessage: null,
      error: null,
    }),

  beginStream: (question) =>
    set({
      pendingUserMessage: question,
      lastQuestion: question,
      stage: null,
      streamingSources: [],
      streamedContent: null,
      streamedMessage: null,
      error: null,
      isStreaming: true,
    }),

  setStage: (stage) => set({ stage }),
  setSources: (sources) => set({ streamingSources: sources }),
  appendToken: (delta) =>
    set((state) => ({ streamedContent: (state.streamedContent ?? '') + delta })),
  setStreamedMessage: (message) => set({ streamedMessage: message }),
  fail: (message) => set({ error: message, isStreaming: false, stage: null, streamedContent: null }),

  // pendingUserMessage is intentionally kept: the optimistic user bubble stays
  // visible until the refetched conversation actually contains the message.
  endStream: () =>
    set({
      isStreaming: false,
      stage: null,
      streamedContent: null,
      streamedMessage: null,
      streamingSources: [],
      error: null,
    }),

  abortStream: () =>
    set({
      isStreaming: false,
      stage: null,
      pendingUserMessage: null,
      streamedContent: null,
      streamedMessage: null,
      streamingSources: [],
      error: null,
    }),

  // Cross-page handoff: a question queued by the search page's "Ask in chat"
  // deep-link. Consumed (and cleared) by ChatPage once a conversation exists.
  setQueuedQuestion: (question) => set({ queuedQuestion: question }),
}))
