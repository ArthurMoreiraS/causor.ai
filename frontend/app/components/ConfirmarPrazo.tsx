"use client";

import { useEffect, useState } from "react";
import { confirmarPrazoIntimacao, type Prazo, type PrazoAlternativa, type PrazoAnalise } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { formatDate } from "@/lib/format";

/** Revisão do prazo de uma intimação.
 *
 * Com sugestão por tipo de ato, o advogado escolhe a providência e confirma em
 * um clique; o cálculo usa a publicação no DJEN e o fundamento da opção. O
 * formulário manual continua disponível para ajustar base, duração e feriados.
 */
export default function ConfirmarPrazo({ intimacaoId, analise, onConfirmed }: {
  intimacaoId: number; analise?: PrazoAnalise | null; onConfirmed?: (prazo: Prazo) => void;
}) {
  const options = analise?.alternativas ?? [];
  // A duração da triagem não é o prazo do ato: o advogado informa o real.
  const suggestedDays = analise?.origem_duracao === "triagem" ? null : analise?.dias;
  const [choice, setChoice] = useState(0);
  const [base, setBase] = useState(analise?.publicacao ?? "");
  const [dias, setDias] = useState(suggestedDays ? String(suggestedDays) : "");
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
    setDias(suggestedDays ? String(suggestedDays) : "");
  }, [analise?.publicacao, suggestedDays, edited]);

  async function confirmar(payload: { dias: number; dias_uteis: boolean; justificativa: string; descricao?: string; dias_sem_expediente: string[] }) {
    setBusy(true); setError(null);
    try {
      const prazo = await confirmarPrazoIntimacao(intimacaoId, { data_base: base, ...payload });
      setResult(prazo);
      onConfirmed?.(prazo);
    } catch (err) { setError(humanError(err, "Falha ao confirmar prazo")); }
    finally { setBusy(false); }
  }

  function confirmarOpcao(option: PrazoAlternativa) {
    void confirmar({
      dias: option.dias, dias_uteis: true, descricao: option.ato_cabivel, dias_sem_expediente: [],
      justificativa: `${option.ato_cabivel}: ${option.fundamento}; ${option.dias} dias úteis contados da publicação no DJEN.`,
    });
  }

  if (result) {
    return <p role="status" className="deadlineConfirmed">
      Prazo confirmado: <strong>{result.descricao ?? "Prazo"}</strong> até <strong>{formatDate(result.data_fatal)}</strong>.
    </p>;
  }
  return <div className="deadlineReview">
    {options.length && base ? <fieldset className="deadlineOptions">
      <legend>Prazo sugerido pelo tipo de ato — escolha a providência</legend>
      {options.map((option, index) => (
        <label key={option.ato_cabivel} className={`deadlineOption${index === choice ? " selected" : ""}`}>
          <input type="radio" name={`prazo-${intimacaoId}`} checked={index === choice} onChange={() => setChoice(index)} />
          <span className="deadlineOptionMain">
            <strong>{option.ato_cabivel}</strong>
            <span>{option.dias} dias úteis · vence em <strong>{formatDate(option.data_fatal)}</strong></span>
            <small><a href={option.fonte} target="_blank" rel="noreferrer">{option.fundamento}</a></small>
          </span>
        </label>
      ))}
      <p className="deadlineOptionsHint">
        Publicação considerada: {formatDate(base)}. Confirme o cabimento para a parte representada,
        prazo em dobro e feriados ou suspensões locais antes de confirmar.
      </p>
      <button className="toolbarButton primary compact" disabled={busy} onClick={() => confirmarOpcao(options[choice])}>
        Confirmar {options[choice].ato_cabivel.split(" (")[0]} até {formatDate(options[choice].data_fatal)}
      </button>
    </fieldset> : null}
    <details className="officeForm deadlineReviewForm" open={!options.length && Boolean(analise?.publicacao)} onChange={() => setEdited(true)}>
      <summary>{options.length ? "Ajustar manualmente" : "Revisar e calcular prazo"}</summary>
      {analise?.evidencia ? <p>Trecho usado na sugestão: “{analise.evidencia}”</p> : null}
      <p>Use esta contagem quando forem aplicáveis o calendário nacional e o recesso cível. Informe os dias sem expediente e as suspensões locais que faltarem.</p>
      <label>Data base confirmada (excluída da contagem)<input type="date" value={base} onChange={(e) => setBase(e.target.value)} /></label>
      <label>Duração em dias<input type="number" min={1} max={3650} value={dias} onChange={(e) => setDias(e.target.value)} /></label>
      <label className="deadlineCheckbox"><input type="checkbox" checked={uteis} onChange={(e) => setUteis(e.target.checked)} />Contar dias úteis</label>
      <label>Datas adicionais sem expediente (AAAA-MM-DD, separadas por vírgula)<input value={excecoes} onChange={(e) => setExcecoes(e.target.value)} /></label>
      <label>Fundamento da duração e da data base<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
      <button className="toolbarButton compact" disabled={busy || !base || Number(dias) < 1 || reason.trim().length < 20}
        onClick={() => void confirmar({ dias: Number(dias), dias_uteis: uteis, justificativa: reason,
          dias_sem_expediente: excecoes.split(/[\s,;]+/).filter(Boolean) })}>Confirmar e calcular prazo</button>
    </details>
    {error && <p role="alert">{error}</p>}
  </div>;
}
