import { ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

// Controlled and never dismissed by Esc or outside click: only the accept button closes it.
export function PrivacyDialog({ open, onAccept }: { open: boolean; onAccept: () => void }) {
  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent showCloseButton={false} className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-primary" aria-hidden />
            Antes de empezar
          </DialogTitle>
          <DialogDescription>
            Leé cómo tratamos tus consultas en este piloto.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-3 text-sm">
          <li>
            <strong>Qué se guarda:</strong> tu pregunta (con datos personales ocultos), el tema,
            la respuesta dada y el tiempo que tardó. No pedimos registro.
          </li>
          <li>
            <strong>Datos ocultos:</strong> cédulas, cuentas IBAN, teléfonos y correos se
            reemplazan automáticamente antes de procesar y de guardar. Aun así, no escribas
            nombres ni datos de terceros.
          </li>
          <li>
            <strong>Proveedor de IA fuera del país:</strong> en este piloto tus consultas se
            procesan con el tier gratuito de Google Gemini. Ahí Google puede usar las entradas y
            salidas para mejorar sus productos, y personas revisoras pueden leerlas. En
            producción se usaría un plan pago, donde los datos no se usan para eso.
          </li>
        </ul>
        <DialogFooter>
          <Button type="button" onClick={onAccept} autoFocus>
            Entiendo y acepto
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
