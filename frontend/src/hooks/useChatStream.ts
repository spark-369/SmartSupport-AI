/** useChatStream — drives the SSE lifecycle for the active conversation.

* Retries once through the single-flight token refresh when the access token
  has expired (SSE requests bypass the `api.ts` wrapper).
* Aborts any in-flight stream when the conversation changes or the hook unmounts.
 */

import { useCallback, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { getAccessToken, refreshAccessToken } from '@/lib/api'
import { streamSSE } from '@/lib/sse'
import { queryKeys } from '@/hooks/queries'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import type { ChatStage, Message, SourceRef } from '@/types'

const API_BASE = '/api/v1'
const AUTH_ERROR = /401|unauthorized|expired|credentials|bearer|token/i

interface DonePayload {
  conversation_id: string
  assistant_message_id: string
  title: string | null
  latency_ms: number
}

export function useChatStream(conversationId: string | null) {
  const qc = useQueryClient()
  const isStreaming = useChatStore((s) => s.isStreaming)
  const beginStream = useChatStore((s) => s.beginStream)
  const setStage = useChatStore((s) => s.setStage)
  const setSources = useChatStore((s) => s.setSources)
  const appendToken = useChatStore((s) => s.appendToken)
  const setStreamedMessage = useChatStore((s) => s.setStreamedMessage)
  const fail = useChatStore((s) => s.fail)
  const endStream = useChatStore((s) => s.endStream)
  const abortStream = useChatStore((s) => s.abortStream)
  const abortRef = useRef<(() => void) | null>(null)

  // Abort any in-flight stream when the hook unmounts or the conversation changes.
  useEffect(() => () => abortRef.current?.(), [conversationId])

  const send = useCallback(
    (content: string) => {
      if (!conversationId || isStreaming) return
      beginStream(content)
      let retriedAfterRefresh = false

      const handleAuthFailure = () => {
        useAuthStore.getState().clear()
        window.dispatchEvent(new CustomEvent('ss:session-expired'))
        fail('Session expired. Please sign in again.')
      }

      const start = () => {
        abortRef.current = streamSSE(
          `${API_BASE}/conversations/${conversationId}/messages/stream`,
          { content },
          getAccessToken(),
          {
            onEvent: (type, data) => {
              switch (type) {
                case 'status':
                  setStage((data as { stage: ChatStage }).stage)
                  break
                case 'sources':
                  setSources((data as { sources: SourceRef[] }).sources)
                  break
                case 'token':
                  appendToken((data as { delta: string }).delta)
                  break
                case 'answer':
                  setStreamedMessage((data as { message: Message }).message)
                  break
                case 'done': {
                  const payload = data as DonePayload
                  if (payload.title) {
                    void qc.invalidateQueries({ queryKey: queryKeys.conversations })
                  }
                  void qc.invalidateQueries({ queryKey: queryKeys.conversation(conversationId) })
                  endStream()
                  break
                }
                case 'error':
                  fail((data as { message: string }).message)
                  break
              }
            },
            onError: (error) => {
              if (!AUTH_ERROR.test(error.message)) {
                fail(error.message)
                return
              }
              if (retriedAfterRefresh) {
                handleAuthFailure()
                return
              }
              // Access token most likely expired — refresh once (single-flight
              // inside the api wrapper) and restart the stream transparently.
              retriedAfterRefresh = true
              void refreshAccessToken().then((token) => {
                if (token) {
                  start()
                } else {
                  handleAuthFailure()
                }
              })
            },
            onClose: () => {
              // Defensive: stream closed without an explicit done/error.
              if (useChatStore.getState().isStreaming) endStream()
            },
          },
        )
      }

      start()
    },
    [conversationId, isStreaming, beginStream, setStage, setSources, appendToken, setStreamedMessage, fail, endStream, qc],
  )

  const cancel = useCallback(() => {
    abortRef.current?.()
    abortStream()
  }, [abortStream])

  return { send, cancel, isStreaming }
}
