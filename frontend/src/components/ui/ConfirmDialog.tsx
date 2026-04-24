import type { ReactNode } from "react";
import { AlertTriangle, Info, Trash2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

type Tone = "danger" | "warning" | "info";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: ReactNode;
  /** Extra detail — appears in a quoted block (e.g. the item being deleted). */
  detail?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: Tone;
  loading?: boolean;
}

const toneSpec: Record<
  Tone,
  { bg: string; text: string; ring: string; icon: ReactNode }
> = {
  danger: {
    bg: "bg-rose-100",
    text: "text-rose-700",
    ring: "ring-rose-200",
    icon: <Trash2 className="h-5 w-5" />,
  },
  warning: {
    bg: "bg-amber-100",
    text: "text-amber-700",
    ring: "ring-amber-200",
    icon: <AlertTriangle className="h-5 w-5" />,
  },
  info: {
    bg: "bg-sky-100",
    text: "text-sky-700",
    ring: "ring-sky-200",
    icon: <Info className="h-5 w-5" />,
  },
};

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  detail,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "danger",
  loading,
}: ConfirmDialogProps) {
  const spec = toneSpec[tone];
  const resolvedConfirmLabel =
    confirmLabel ?? (tone === "danger" ? "Delete" : "Confirm");

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      disableBackdropClose={loading}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            loading={loading}
          >
            {resolvedConfirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-3">
        <span
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ring-1 ring-inset ${spec.bg} ${spec.text} ${spec.ring}`}
        >
          {spec.icon}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          {description && (
            <p className="mt-1 text-sm text-slate-600">{description}</p>
          )}
          {detail && (
            <p className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 break-words">
              {detail}
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}
