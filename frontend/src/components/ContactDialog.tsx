import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { sendDerivacion } from "@/lib/api"

interface Props {
  interactionId: number | null
  onClose: () => void
  onDone: () => void
}

export function ContactDialog({ interactionId, onClose, onDone }: Props) {
  const [contact, setContact] = useState("")
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  const submit = async (ev: FormEvent) => {
    ev.preventDefault()
    if (!consent) {
      setError("Necesitamos tu consentimiento para guardar tu contacto.")
      return
    }
    if (interactionId === null) return
    setBusy(true)
    try {
      await sendDerivacion(interactionId, contact.trim())
      setContact("")
      setConsent(false)
      setError("")
      onDone()
    } catch {
      setError("No pudimos guardar tu contacto. Intentá de nuevo.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={interactionId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Pedir revisión de un contador</DialogTitle>
          <DialogDescription>
            Dejanos un medio de contacto y una persona contadora te escribe.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="dato-contacto">Tu correo o teléfono</Label>
            <Input
              id="dato-contacto"
              required
              minLength={3}
              maxLength={200}
              value={contact}
              onChange={(e) => setContact(e.target.value)}
            />
          </div>
          <div className="flex items-start gap-2">
            <Checkbox
              id="acepto"
              checked={consent}
              onCheckedChange={(v) => setConsent(v === true)}
              className="mt-0.5"
            />
            <Label htmlFor="acepto" className="text-sm leading-snug font-normal">
              Acepto que Kontia guarde este dato para que un contador me contacte sobre mi
              consulta.
            </Label>
          </div>
          <p role="status" className="min-h-5 text-sm text-destructive">
            {error}
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              Enviar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
