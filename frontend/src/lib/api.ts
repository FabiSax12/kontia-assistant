export interface Ficha {
  titulo: string
  fecha_revision: string
  fuente: string
}

export interface Calculo {
  tool: string
  datos: Record<string, number | string>
}

export interface ChatResponse {
  respuesta: string
  ficha?: Ficha | null
  calculo?: Calculo | null
  derivado?: boolean
  interaction_id?: number | null
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error("http " + r.status)
  return r.json()
}

export const sendChat = (session_id: string, mensaje: string) =>
  post<ChatResponse>("/api/chat", { session_id, mensaje })

export const sendFeedback = (interaction_id: number, rating: number) =>
  post("/api/feedback", { interaction_id, rating })

export const sendDerivacion = (interaction_id: number, contacto: string) =>
  post("/api/derivacion", { interaction_id, contacto, acepto: true })
