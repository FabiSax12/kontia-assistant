import { useState } from "react"
import { MessageSquareText, TriangleAlert } from "lucide-react"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input"
import { Shimmer } from "@/components/ai-elements/shimmer"
import { Suggestion } from "@/components/ai-elements/suggestion"
import { ContactDialog } from "@/components/ContactDialog"
import { FichaCard } from "@/components/FichaCard"
import { PrivacyDialog } from "@/components/PrivacyDialog"
import { ResponseActions } from "@/components/ResponseActions"
import { Button } from "@/components/ui/button"
import { useKontiaChat } from "@/hooks/useKontiaChat"
import { readStore, writeStore } from "@/lib/storage"

const WELCOME =
  "Hola, soy el Asistente Kontia. Preguntame sobre aguinaldo, cargas sociales de la CCSS, INS o Hacienda."

const SUGGESTIONS = [
  "¿Cuándo pago el aguinaldo?",
  "Calcular cargas sociales de ₡500 000",
  "¿Cuánto me cuesta un empleado con salario de ₡600 000?",
  "¿Cómo presento la planilla de la CCSS?",
  "¿Cuándo vence la declaración del IVA?",
]

export default function App() {
  const { messages, status, send, notify } = useKontiaChat()
  const [privacyOk, setPrivacyOk] = useState(() => readStore("kontia_privacidad_ok") === "1")
  const [contactFor, setContactFor] = useState<number | null>(null)

  const acceptPrivacy = () => {
    writeStore("kontia_privacidad_ok", "1")
    setPrivacyOk(true)
  }
  const busy = status === "submitted"

  return (
    <div className="mx-auto flex h-dvh max-w-3xl flex-col">
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <div
          className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"
          aria-hidden
        >
          <MessageSquareText className="size-5" />
        </div>
        <div>
          <h1 className="text-base leading-tight font-semibold">Kontia</h1>
          <p className="text-xs text-muted-foreground">
            Orientación sobre CCSS, Hacienda, INS y aguinaldo para tu PYME
          </p>
        </div>
      </header>

      <Conversation className="min-h-0">
        <ConversationContent className="gap-6">
          {messages.length === 0 ? (
            <ConversationEmptyState className="min-h-[40vh]">
              <div className="flex max-w-md flex-col items-center gap-2">
                <h2 className="text-lg font-semibold">¿En qué te puedo ayudar?</h2>
                <p className="text-sm text-muted-foreground">{WELCOME}</p>
              </div>
              <div className="mt-2 flex max-w-xl flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <Suggestion
                    key={s}
                    suggestion={s}
                    disabled={!privacyOk || busy}
                    onClick={send}
                    className="h-auto whitespace-normal py-1.5 text-left"
                  />
                ))}
              </div>
            </ConversationEmptyState>
          ) : (
            messages.map((m) => (
              <Message key={m.id} from={m.role}>
                <MessageContent>
                  {m.role === "user" ? (
                    <span className="whitespace-pre-wrap">{m.text}</span>
                  ) : (
                    <MessageResponse>{m.text}</MessageResponse>
                  )}
                </MessageContent>
                {m.data?.ficha && <FichaCard ficha={m.data.ficha} calculo={m.data.calculo} />}
                {m.data?.derivado && (
                  <div className="flex w-fit max-w-md items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                    <div>
                      Tu consulta necesita a una persona.{" "}
                      {m.data.interaction_id != null && (
                        <Button
                          variant="link"
                          className="h-auto p-0 text-inherit underline"
                          onClick={() => setContactFor(m.data!.interaction_id!)}
                        >
                          Dejar mi contacto
                        </Button>
                      )}
                    </div>
                  </div>
                )}
                {m.data?.interaction_id != null && (
                  <ResponseActions
                    interactionId={m.data.interaction_id}
                    onRequestReview={setContactFor}
                  />
                )}
              </Message>
            ))
          )}
          {busy && (
            <Message from="assistant" aria-live="polite">
              <Shimmer className="text-sm">Pensando…</Shimmer>
            </Message>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="px-4 pt-2 pb-4">
        <PromptInput onSubmit={({ text }) => send(text)}>
          <PromptInputBody>
            <PromptInputTextarea
              aria-label="Tu consulta"
              maxLength={800}
              disabled={!privacyOk}
              placeholder="Escribí tu consulta (sin nombres ni datos de terceros)"
            />
          </PromptInputBody>
          <PromptInputFooter>
            <span className="text-xs text-muted-foreground">
              Orientación general, no reemplaza a un contador.
            </span>
            <PromptInputSubmit status={status} disabled={!privacyOk || busy} aria-label="Enviar" />
          </PromptInputFooter>
        </PromptInput>
      </div>

      <PrivacyDialog open={!privacyOk} onAccept={acceptPrivacy} />
      <ContactDialog
        interactionId={contactFor}
        onClose={() => setContactFor(null)}
        onDone={() => {
          setContactFor(null)
          notify("Listo, un contador te va a contactar. Gracias.")
        }}
      />
    </div>
  )
}
