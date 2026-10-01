"use client";

import { useEffect, useState } from "react";
import { confirmarPrazoIntimacao, type Prazo } from "@/lib/api";
import { humanError } from "@/lib/errors";

export default function ConfirmarPrazo({ intimacaoId, analise, onConfirmed }: { intimacaoId: number; analise?: { publicacao?: string; dias?: number | null; evidencia?: string | null } | null; onConfirmed?: (prazo: Prazo) => void }) {
  const [base, setBase] = useState(analise?.publicacao ?? "");
  const [dias, setDias] = useState(analise?.dias ? String(analise.dias) : "");
  const [uteis, setUteis] = useState(true);
  const [excecoes, setExcecoes] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Prazo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edited, setEdited] = useState(false);
  useEffect(() => {
    if (edited) return;
    setBase(analise?.publicacao ?? "");
    setDias(analise?.dias ? String(analise.dias) : "");
  }, [analise?.publicacao, analise?.dias, edited]);
  async function confirmar() {
    setBusy(true); setError(null);
    try {
      const prazo = await confirmarPrazoIntimacao(intimacaoId, {
        data_base: base, dias: Number(dias), dias_uteis: uteis, justificativa: reason,
        dias_sem_expediente: excecoes.split(/[\s,;]+/).filter(Boolean)
      });
      setResult(prazo);
      onConfirmed?.(prazo);
    } catch (err) { setError(humanError(err, "Falha ao confirmar prazo")); }
    finally { setBusy(false); }
  }
  if (result) return <p role="status">Prazo registrado: {result.data_fatal.split("-").reverse().join("/")}.</p>;
  return <details className="officeForm deadlineReviewForm" open={Boolean(analise?.publicacao)} onChange={() => setEdited(true)}>
    <summary>Revisar e calcular prazo</summary>
    {analise?.evidencia ? <p>Trecho usado na sugestão: “{analise.evidencia}”</p> : null}
    <p>Use esta contagem quando forem aplicáveis o calendário nacional e o recesso cível. Informe os dias sem expediente e as suspensões locais que faltarem.</p>
    <label>Data base confirmada (excluída da contagem)<input type="date" value={base} onChange={(e) => setBase(e.target.value)} /></label>
    <label>Duração em dias<input type="number" min={1} max={3650} value={dias} onChange={(e) => setDias(e.target.value)} /></label>
    <label className="deadlineCheckbox"><input type="checkbox" checked={uteis} onChange={(e) => setUteis(e.target.checked)} />Contar dias úteis</label>
    <label>Datas adicionais sem expediente (AAAA-MM-DD, separadas por vírgula)<input value={excecoes} onChange={(e) => setExcecoes(e.target.value)} /></label>
    <label>Fundamento da duração e da data base<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
    <button className="toolbarButton compact" disabled={busy || !base || Number(dias) < 1 || reason.trim().length < 20} onClick={() => void confirmar()}>Confirmar e calcular prazo</button>
    {error && <p role="alert">{error}</p>}
  </details>;
}
