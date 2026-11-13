import { useState } from "react"
import { Star, UserRound } from "lucide-react"
import { MessageAction, MessageActions } from "@/components/ai-elements/message"
import { Button } from "@/components/ui/button"
import { sendFeedback } from "@/lib/api"
import { cn } from "@/lib/utils"

interface Props {
  interactionId: number
  onRequestReview: (interactionId: number) => void
}

export function ResponseActions({ interactionId, onRequestReview }: Props) {
  const [rating, setRating] = useState<number | null>(null)

  const rate = async (n: number) => {
    if (rating !== null) return
    try {
      await sendFeedback(interactionId, n)
      setRating(n)
    } catch {
      // offline: the user can try again
    }
  }

  return (
    <MessageActions className="flex-wrap gap-x-3 gap-y-1">
      <span className="text-xs text-muted-foreground" id={`rate-${interactionId}`}>
        {rating === null ? "¿Te sirvió?" : "¡Gracias por tu calificación!"}
      </span>
      <div role="group" aria-labelledby={`rate-${interactionId}`} className="flex">
        {[1, 2, 3, 4, 5].map((n) => (
          <MessageAction
            key={n}
            label={`Calificar con ${n}`}
            disabled={rating !== null}
            onClick={() => rate(n)}
          >
            <Star
              className={cn(
                "size-4",
                rating !== null && n <= rating && "fill-amber-400 text-amber-400",
              )}
            />
          </MessageAction>
        ))}
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 text-xs text-muted-foreground"
        onClick={() => onRequestReview(interactionId)}
      >
        <UserRound className="size-3.5" aria-hidden />
        Pedir revisión de un contador
      </Button>
    </MessageActions>
  )
}
