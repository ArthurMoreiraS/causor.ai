"use client";

import { Loader2, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { ChatTurn, enviarMensagemChat, ProposedAction } from "@/lib/api";

export default function AssistantWorkspace({
  offline,
  onConfirmAction
}: {
  offline: boolean;
  onConfirmAction: (action: ProposedAction) => Promise<void>;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<ProposedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(textFromSuggestion?: string) {
    const text = (textFromSuggestion ?? input).trim();
    if (!text || busy || offline) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const resp = await enviarMensagemChat(next);
      setTurns([
        ...next,
        {
          role: "assistant",
          content: resp.reply || "Recebi a solicitação e preparei os próximos passos."
        }
      ]);
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
      setPending((prev) => prev.filter((item) => item !== action));
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

  const suggestions = [
    "Quais prazos exigem atenção hoje?",
    "Mostre as intimações sem minuta.",
    "Quais minutas aguardam aprovação OAB?"
  ];

  return (
    <section className="assistantWorkspace">
      <div className="chatSurface">
        {turns.length === 0 ? (
          <div className="promptSuggestions">
            {suggestions.map((suggestion) => (
              <button key={suggestion} onClick={() => void send(suggestion)} disabled={offline || busy}>
                <Sparkles size={15} />
                {suggestion}
              </button>
            ))}
          </div>
        ) : (
          <div className="chatTimeline">
            {turns.map((turn, index) => (
              <article className={`chatBubble ${turn.role}`} key={`${turn.role}-${index}`}>
                <span>{turn.content}</span>
              </article>
            ))}
          </div>
        )}

        {pending.length ? (
          <div className="assistantActionShelf">
            {pending.map((action, index) => (
              <article className="assistantActionCard" key={`${action.tipo}-${index}`}>
                <div>
                  <ShieldCheck size={15} />
                  <strong>{action.label}</strong>
                  <span>{action.endpoint}</span>
                </div>
                <div className="proposedActions">
                  <button
                    className="toolbarButton primary"
                    disabled={busy || offline}
                    onClick={() => void confirm(action)}
                  >
                    Confirmar
                  </button>
                  <button
                    className="toolbarButton"
                    disabled={busy}
                    onClick={() => setPending((prev) => prev.filter((item) => item !== action))}
                  >
                    Descartar
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}

        {error ? <div className="assistantError wide">{error}</div> : null}
      </div>

      <form
        className="assistantComposer"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <textarea
          placeholder={offline ? "Backend offline" : "Pergunte ao Causor"}
          value={input}
          disabled={offline || busy}
          rows={1}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <button className="iconButton" disabled={offline || busy || !input.trim()} type="submit">
          {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
        </button>
      </form>
    </section>
  );
}
