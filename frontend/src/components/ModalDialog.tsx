import React, { useEffect, useId, useRef } from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DialogHeader } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

interface ModalDialogProps {
  isOpen: boolean
  onClose: () => void
  title: string
  maxWidthClass?: string
  children: React.ReactNode
}

/**
 * Native <dialog> component adhering to modern-web-guidance (`dialog`) & shadcn composition:
 * - Opens via `.showModal()` for native top-layer, inert background, focus containment, and Esc support
 * - Avoids redundant role="dialog" or aria-modal
 * - Resets dialog.returnValue = '' on close to prevent stale returnValue leaks
 * - Scopes layout display to open state only (`open:flex`)
 */
export const ModalDialog: React.FC<ModalDialogProps> = ({
  isOpen,
  onClose,
  title,
  maxWidthClass = "max-w-2xl",
  children,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (isOpen && !dialog.open) {
      dialog.showModal()
    } else if (!isOpen && dialog.open) {
      dialog.close()
    }
  }, [isOpen])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    const handleClose = () => {
      dialog.returnValue = ""
      onClose()
    }

    dialog.addEventListener("close", handleClose)
    return () => dialog.removeEventListener("close", handleClose)
  }, [onClose])

  return (
    <dialog
      ref={dialogRef}
      data-slot="dialog-content"
      aria-labelledby={titleId}
      className={cn(
        "m-auto max-h-[90vh] w-[calc(100%-2rem)] rounded-xl border bg-popover p-0 text-popover-foreground shadow-2xl ring-1 ring-foreground/10 open:flex open:flex-col",
        maxWidthClass
      )}
    >
      <DialogHeader className="flex flex-row items-center justify-between gap-3 rounded-t-xl bg-muted/40 px-6 py-4">
        <h2
          id={titleId}
          data-slot="dialog-title"
          className="font-heading text-lg font-bold text-foreground"
        >
          {title}
        </h2>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => dialogRef.current?.close()}
          aria-label="Close modal"
        >
          <X aria-hidden="true" />
        </Button>
      </DialogHeader>
      <Separator />
      <div className="overflow-y-auto p-6">{children}</div>
    </dialog>
  )
}
