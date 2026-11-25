/** Fetch-based SSE client (supports POST + Authorization headers). */

export interface SSECallbacks {
  onEvent: (type: string, data: unknown) => void
  onError?: (error: Error) => void
  onClose?: () => void
}

/**
 * POST an SSE endpoint and dispatch parsed `event:`/`data:` frames to callbacks.
 * The returned abort function cancels the underlying fetch.
 */
export function streamSSE(
  path: string,
  body: unknown,
  token: string | null,
  callbacks: SSECallbacks,
): () => void {
  const controller = new AbortController()

  void (async () => {
    try {
      const response = await fetch(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
        credentials: 'include',
      })

      if (!response.ok || !response.body) {
        const text = await response.text().catch(() => '')
        let message = response.statusText
        try {
          message = JSON.parse(text)?.error?.message ?? message
        } catch {
          /* keep statusText */
        }
        callbacks.onError?.(new Error(message))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let separator: number
        while ((separator = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, separator)
          buffer = buffer.slice(separator + 2)

          let type = 'message'
          const dataLines: string[] = []
          for (const line of frame.split('\n')) {
            if (line.startsWith('event: ')) type = line.slice(7).trim()
            else if (line.startsWith('data: ')) dataLines.push(line.slice(6))
          }
          if (dataLines.length === 0) continue
          try {
            callbacks.onEvent(type, JSON.parse(dataLines.join('\n')))
          } catch {
            callbacks.onEvent(type, dataLines.join('\n'))
          }
        }
      }
      callbacks.onClose?.()
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        callbacks.onClose?.()
      } else {
        callbacks.onError?.(error as Error)
      }
    }
  })()

  return () => controller.abort()
}
