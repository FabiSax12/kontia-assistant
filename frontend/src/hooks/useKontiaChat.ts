import { useCallback, useRef, useState } from "react"
import { sendChat, type ChatResponse } from "@/lib/api"
import { getSessionId } from "@/lib/storage"

export interface ChatMessage {
  id: number
  role: "user" | "assistant"
  text: string
  data?: ChatResponse
}

export type ChatStatus = "ready" | "submitted"

const CONNECTION_ERROR =
  "No pude conectarme en este momento. Revisá tu conexión e intentá de nuevo."

export function useKontiaChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>("ready")
  const sessionId = useRef(getSessionId())
  const nextId = useRef(1)

  const append = useCallback((msg: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { ...msg, id: nextId.current++ }])
  }, [])

  const send = useCallback(
    async (text: string) => {
      const clean = text.trim()
      if (!clean || status !== "ready") return
      append({ role: "user", text: clean })
      setStatus("submitted")
      try {
        const data = await sendChat(sessionId.current, clean)
        append({ role: "assistant", text: data.respuesta, data })
      } catch {
        append({ role: "assistant", text: CONNECTION_ERROR })
      } finally {
        setStatus("ready")
      }
    },
    [append, status],
  )

  const notify = useCallback(
    (text: string) => append({ role: "assistant", text }),
    [append],
  )

  return { messages, status, send, notify }
}
