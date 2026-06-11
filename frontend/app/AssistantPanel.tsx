"use client";

import { Bot, Loader2, Send, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { ChatTurn, enviarMensagemChat, ProposedAction } from "@/lib/api";

type Props = {
  processoId?: number;
  offline: boolean;
  onConfirmAction: (action: ProposedAction) => Promise<void>;
  onClose: () => void;
};

export default function AssistantPanel({
  processoId,
  offline,
  onConfirmAction,
  onClose
}: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<ProposedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const resp = await enviarMensagemChat(next, processoId);
      setTurns([...next, { role: "assistant", content: resp.reply }]);
      setPending(resp.proposed_actions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no assistente");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(action: ProposedAction) {
    setBusy(true);
    setError(null);
    try {
      await onConfirmAction(action);
      setPending((prev) => prev.filter((a) => a !== action));
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: `Ação executada: ${action.label}.` }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ação não concluída");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="assistantPanel">
      <header className="assistantHead">
        <div>
          <Bot size={16} /> <strong>Assistente Causor</strong>
        </div>
        <button className="iconButton" onClick={onClose} title="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="assistantBody">
        {turns.length === 0 ? (
          <p className="assistantHint">
            Pergunte sobre prazos, intimações ou peça uma ação (gerar minuta,
            marcar prazo). Ações irreversíveis sempre passam pela sua confirmação.
          </p>
        ) : null}
        {turns.map((turn, i) => (
          <div key={i} className={`chatTurn ${turn.role}`}>
            <span>{turn.content}</span>
          </div>
        ))}

        {pending.map((action, i) => (
          <div className="proposedAction" key={`${action.tipo}-${i}`}>
            <div>
              <ShieldCheck size={14} /> <strong>{action.label}</strong>
              <small>{action.endpoint}</small>
            </div>
            <div className="proposedActions">
              <button
                className="toolbarButton primary"
                disabled={busy || offline}
                onClick={() => confirm(action)}
              >
                Confirmar
              </button>
              <button
                className="toolbarButton"
                disabled={busy}
                onClick={() => setPending((prev) => prev.filter((a) => a !== action))}
              >
                Descartar
              </button>
            </div>
          </div>
        ))}

        {error ? <div className="assistantError">{error}</div> : null}
      </div>

      <footer className="assistantFoot">
        <input
          placeholder={offline ? "Backend offline" : "Pergunte ao assistente…"}
          value={input}
          disabled={offline || busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void send();
          }}
        />
        <button className="iconButton" disabled={offline || busy} onClick={() => void send()}>
          {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
        </button>
      </footer>
    </aside>
  );
}
