"use client";
import { useState } from "react";
import { criarPendenciaTrabalho, buscarFontesTrabalho, conferirEvidencias, gerarMinutaTrabalho, prepararEvidencias, type FonteTrabalho, type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
import DocumentEvidenceDialog from "./DocumentEvidenceDialog";
import { LoadingButton } from "./ui";

export default function WorkEvidence({ work, disabled, onSaved, onOpenDraft }: {
  work: Trabalho; disabled: boolean; onSaved: (work: Trabalho) => void; onOpenDraft: (id: number) => void;
}) {
  const [questions, setQuestions] = useState(work.evidencias?.perguntas.join("\n") || "");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<FonteTrabalho[]>([]);
  const [pinned, setPinned] = useState<number[]>([]);
  const [source, setSource] = useState<FonteTrabalho | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [checked, setChecked] = useState(false);
  const evidence = work.evidencias;
  const stale = work.evidencias_atuais === false;
  async function act(name: string, action: () => Promise<void>) {
    if (busy || disabled) return; setBusy(name); setError(null); setMessage("");
    try { await action(); } catch (err) { setError(humanError(err, "Não foi possível concluir a etapa")); }
    finally { setBusy(null); }
  }
  function open(id: number) { const found = evidence?.citations.find(item => item.chunk_id === id); if (found) setSource(found); }
  return <section id="work-evidence" tabIndex={-1} className="legalWorkStage workStageAnchor" aria-label="Evidências e minuta">
    <h3>3. Evidências para esta providência</h3>
    <p>Busque nos documentos originais, fixe fontes relevantes e confira a análise antes de redigir.</p>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {message ? <p role="status">{message}</p> : null}
    {stale ? <p role="alert">Revisão necessária. {work.motivo_revisao}</p> : null}
    <div className="officeForm"><label>Pontos que precisam ser respondidos<textarea rows={3} value={questions} disabled={disabled || Boolean(busy)}
      onChange={e => setQuestions(e.target.value)} placeholder="Uma pergunta por linha. Ex.: Há prova de pagamento?" /></label>
      <label>Buscar no texto original<input maxLength={500} value={query} disabled={disabled || Boolean(busy)} onChange={e => setQuery(e.target.value)} /></label>
      <LoadingButton loading={busy === "search"} disabled={disabled || Boolean(busy) || !query.trim()} onClick={() => void act("search", async () => setHits((await buscarFontesTrabalho(work, query)).items))}>Buscar fontes</LoadingButton>
      {hits.map(hit => <article className="legalEvidenceQuote" key={hit.chunk_id}><p>{hit.quote}</p><div className="officeToolbar">
        <button className="toolbarButton compact" onClick={() => setSource(hit)}>{hit.nome || `Documento ${hit.documento_id}`} · p. {hit.pagina}</button>
        <label className="officeCheckbox"><input type="checkbox" checked={pinned.includes(hit.chunk_id)} disabled={disabled || Boolean(busy)}
          onChange={e => setPinned(values => e.target.checked ? [...values, hit.chunk_id] : values.filter(id => id !== hit.chunk_id))} /> Usar esta fonte na análise</label></div></article>)}
      {!work.escopo ? <p role="status">Registre o escopo dos documentos na etapa anterior para preparar a análise.</p> : null}
      <LoadingButton loading={busy === "prepare"} disabled={disabled || Boolean(busy) || !work.escopo} onClick={() => void act("prepare", async () => {
        const result = await prepararEvidencias(work, questions.split("\n").filter(line => line.trim()), pinned); setChecked(false); onSaved(result);
      })}>{evidence ? "Atualizar análise das evidências" : "Preparar análise das evidências"}</LoadingButton>
    </div>
    {evidence ? <>
      <p className="officeHint">Análise proposta para revisão. Uma referência existente não certifica que a conclusão está correta.</p>
      {([ ["Fatos e alegações", evidence.analise.fatos], ["Cronologia", evidence.analise.cronologia], ["Contradições e prova contrária", evidence.analise.contradicoes] ] as const).map(([title, facts]) =>
        <section key={title}><h4>{title}</h4>{facts.length ? facts.map((fact, index) => <article className="legalEvidenceQuote" key={index}><p>{fact.texto}</p><small>{fact.natureza.replaceAll("_", " ")}</small>
          <div className="officeToolbar">{fact.fontes.map(id => <button key={id} className="toolbarButton compact" onClick={() => open(id)}>Conferir fonte {evidence.citations.find(c => c.chunk_id === id)?.pagina ? `· p. ${evidence.citations.find(c => c.chunk_id === id)?.pagina}` : ""}</button>)}</div></article>) : <p>Nenhum ponto identificado pela análise; confira o acervo.</p>}</section>)}
      <h4>Lacunas e documentos necessários</h4>
      {evidence.analise.lacunas.map((gap, index) => <article className="legalEvidenceQuote" key={index}><p>{gap}</p>
        <button className="toolbarButton compact" disabled={disabled || Boolean(busy)}
          onClick={() => void act(`task-${index}`, async () => {
            const task = await criarPendenciaTrabalho(work, index);
            setMessage(`Pendência #${task.id} vinculada ao trabalho em Tarefas e pendências.`);
          })}>Criar pendência documental</button></article>)}
      {evidence.avisos.map((warning, index) => <p className="officeHint" key={index}>{warning}</p>)}
      {!evidence.conferida ? <><label className="officeCheckbox"><input type="checkbox" checked={checked} disabled={disabled || Boolean(busy)} onChange={e => setChecked(e.target.checked)} /> Conferi as fontes, os pontos contrários e as lacunas desta análise.</label>
        <LoadingButton loading={busy === "review"} disabled={disabled || Boolean(busy) || !checked || stale} onClick={() => void act("review", async () => onSaved(await conferirEvidencias(work)))}>Registrar conferência</LoadingButton></> : <p role="status">Conferência registrada. Lacunas documentais continuam exigindo acompanhamento.</p>}
      <h3 id="work-draft" tabIndex={-1} className="workStageAnchor">4. Minuta e revisão</h3>
      <LoadingButton loading={busy === "draft"} disabled={disabled || Boolean(busy) || !evidence.conferida || stale} onClick={() => void act("draft", async () => {
        const result = await gerarMinutaTrabalho(work); onSaved(result); if (result.peticao_id) onOpenDraft(result.peticao_id);
      })}>{work.peticao_id ? "Gerar nova versão da minuta" : "Gerar minuta para revisão"}</LoadingButton>
    </> : null}
    {source ? <DocumentEvidenceDialog documentoId={source.documento_id} nome={source.nome || `Documento ${source.documento_id}`} versaoId={source.documento_arquivo_id} pagina={source.pagina} onClose={() => setSource(null)} /> : null}
  </section>;
}
