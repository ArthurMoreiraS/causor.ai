"use client";

import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

type ToastKind = "success" | "error" | "info";

type ToastItem = {
  id: number;
  kind: ToastKind;
  title: string;
  description?: string;
};

type ToastInput = {
  kind?: ToastKind;
  title: string;
  description?: string;
  /** Duração em ms antes do auto-dismiss (padrão 4000). */
  duration?: number;
};

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info } as const;

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

/** Dispara toasts. Deve ser usado dentro de <ToastProvider>. */
export function useToast() {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast deve ser usado dentro de <ToastProvider>");
  return push;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (input: ToastInput) => {
      const id = (idRef.current += 1);
      setToasts((list) => [
        ...list,
        { id, kind: input.kind ?? "info", title: input.title, description: input.description }
      ]);
      const timer = setTimeout(() => dismiss(id), input.duration ?? 4000);
      timers.current.set(id, timer);
    },
    [dismiss]
  );

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((timer) => clearTimeout(timer));
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toastViewport" role="region" aria-label="Notificações" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind];
          return (
            <div className={`toast ${toast.kind}`} key={toast.id} role="status">
              <Icon size={16} aria-hidden="true" />
              <div className="toastBody">
                <strong>{toast.title}</strong>
                {toast.description ? <span>{toast.description}</span> : null}
              </div>
              <button className="toastClose" onClick={() => dismiss(toast.id)} aria-label="Fechar">
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
