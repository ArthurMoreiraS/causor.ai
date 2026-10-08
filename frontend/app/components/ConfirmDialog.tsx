"use client";

import { AlertTriangle } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Modal } from "./ui";

export type ConfirmOptions = {
  title: string;
  description?: ReactNode;
  /** Texto do botão que confirma (padrão "Confirmar"). */
  confirmLabel?: string;
  /** Texto do botão que desiste (padrão "Cancelar"). */
  cancelLabel?: string;
  confirmIcon?: ReactNode;
};

type ConfirmRequest = ConfirmOptions & { id: number };

const ConfirmContext = createContext<((options: ConfirmOptions) => Promise<boolean>) | null>(null);

/**
 * Pede confirmação com o diálogo do Causor, no lugar do window.confirm do
 * navegador. Resolve `true` só quando a pessoa confirma; Esc, clique fora e
 * Cancelar resolvem `false`. Deve ser usado dentro de <ConfirmProvider>.
 */
export function useConfirm() {
  const confirm = useContext(ConfirmContext);
  if (!confirm) throw new Error("useConfirm deve ser usado dentro de <ConfirmProvider>");
  return confirm;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  const pending = useRef<((confirmed: boolean) => void) | null>(null);
  const idRef = useRef(0);

  const settle = useCallback((confirmed: boolean) => {
    const resolve = pending.current;
    pending.current = null;
    setRequest(null);
    resolve?.(confirmed);
  }, []);

  const confirm = useCallback((options: ConfirmOptions) => new Promise<boolean>((resolve) => {
    // A new question supersedes one still open: the old caller gets "no".
    pending.current?.(false);
    pending.current = resolve;
    setRequest({ ...options, id: (idRef.current += 1) });
  }), []);

  useEffect(() => () => pending.current?.(false), []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {request ? <ConfirmCard key={request.id} request={request} onSettle={settle} /> : null}
    </ConfirmContext.Provider>
  );
}

function ConfirmCard({ request, onSettle }: { request: ConfirmRequest; onSettle: (confirmed: boolean) => void }) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  return (
    <Modal onClose={() => onSettle(false)} labelledBy={titleId} className="confirmCard" initialFocus={cancelRef}>
      <div className="confirmIcon danger" aria-hidden="true">
        <AlertTriangle size={18} />
      </div>
      <div className="confirmBody">
        <span className="settingsLabel" id={titleId}>{request.title}</span>
        {request.description ? <p>{request.description}</p> : null}
      </div>
      <div className="modalActions">
        <button ref={cancelRef} type="button" className="toolbarButton compact" onClick={() => onSettle(false)}>
          {request.cancelLabel ?? "Cancelar"}
        </button>
        <button type="button" className="toolbarButton compact danger confirmDanger" onClick={() => onSettle(true)}>
          {request.confirmIcon}
          {request.confirmLabel ?? "Confirmar"}
        </button>
      </div>
    </Modal>
  );
}
