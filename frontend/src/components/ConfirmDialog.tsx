import { useEffect, useId, useRef } from "react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ConfirmDialog({ title, message, confirmLabel = "Delete", onConfirm, onCancel, loading }: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const messageId = useId();

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => { previousFocus?.focus(); };
  }, []);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={titleId}
      aria-describedby={messageId} ref={dialogRef} onKeyDown={(event) => {
        if (event.key === "Escape" && !loading) { event.preventDefault(); onCancel(); }
        if (event.key === "Tab") {
          const buttons = Array.from(dialogRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
          const first = buttons[0]; const last = buttons[buttons.length - 1];
          if (!first) { event.preventDefault(); return; }
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }}>
      <div className="modal">
        <h3 id={titleId}>{title}</h3><p id={messageId}>{message}</p>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel} disabled={loading}>Cancel</button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={loading}>{loading ? "Working…" : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
