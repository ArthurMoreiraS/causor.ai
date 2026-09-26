"use client";
import { useState, type FormEvent } from "react";
import { enviarMensagemChat, type ChatTurn } from "@/lib/api";
import { type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
import { LoadingButton } from "./ui";

export default function WorkAssistant({ work, disabled }: { work: Trabalho; disabled: boolean }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]), [input, setInput] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (disabled || busy || !input.trim()) return;
    const messages: ChatTurn[] = [...turns, { role: "user", content: input }];
    setBusy(true); setError(null); setInput(""); setTurns(messages);
    try {
      const result = await enviarMensagemChat(messages, work.processo_id || undefined, work.id);
      setTurns([...messages, { role: "assistant", content: result.reply + (result.proposed_actions.length ? "\n\nConfira e execute as ações nas etapas deste trabalho. Nenhuma ação foi realizada pelo chat." : "") }]);
    } catch (err) { setError(humanError(err, "Não foi possível consultar o assistente")); }
    finally { setBusy(false); }
  }
  return <details className="legalWorkStage"><summary>Conversar com o assistente sobre este trabalho</summary>
    <p>O assistente consulta o objetivo, as fontes e o estado do pacote deste caso. Revisão e aprovação ficam nas etapas do trabalho.</p>
    <div aria-live="polite">{turns.map((turn, index) => <article className="legalEvidenceQuote" key={index}><strong>{turn.role === "user" ? "Você" : "Causor"}</strong><p>{turn.content}</p></article>)}</div>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    <form className="officeForm" onSubmit={submit}><label>Pergunta sobre este trabalho<textarea value={input} maxLength={5000} disabled={disabled || busy} onChange={e => setInput(e.target.value)} /></label>
      <LoadingButton type="submit" loading={busy} disabled={disabled || !input.trim()}>Consultar assistente</LoadingButton></form>
  </details>;
}
