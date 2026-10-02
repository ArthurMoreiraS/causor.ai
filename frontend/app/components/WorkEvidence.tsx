"use client";
import { useEffect, useRef, useState } from "react";
import { criarPendenciaTrabalho, buscarFontesTrabalho, conferirEvidencias, type FonteTrabalho, type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
import DocumentEvidenceDialog from "./DocumentEvidenceDialog";
import { LoadingButton } from "./ui";
import { useWorkOperation } from "./useWorkOperation";

export default function WorkEvidence({ work, disabled, canDraft = true, onSaved, onOpenDraft, onDirtyChange }: {
  work: Trabalho; disabled: boolean; canDraft?: boolean; onSaved: (work: Trabalho) => void; onOpenDraft: (id: number) => void; onDirtyChange?: (dirty: boolean) => void;
}) {
  const [questions, setQuestions] = useState(work.evidencias?.perguntas.join("\n") || "");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<FonteTrabalho[]>([]);
  const [pinned, setPinned] = useState<number[]>([]);
  const [selectedSources, setSelectedSources] = useState<FonteTrabalho[]>([]);
  const [source, setSource] = useState<FonteTrabalho | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [checked, setChecked] = useState(false);
  const baseline = useRef(work.evidencias?.perguntas.join("\n") || "");
  const searchVersion = useRef(0);
  const mounted = useRef(true);
  const snapshot = `${work.evidencias?.source_fingerprint || ""}:${work.evidencias?.preparada_em || ""}:${JSON.stringify(work.evidencias?.inventario || [])}`;
  const sourceIdentity = `${work.evidencias?.source_fingerprint || ""}:${JSON.stringify(work.evidencias?.inventario || [])}`;
  const identity = `${work.id}:${work.versao}:${snapshot}`;
  const currentIdentity = useRef(identity);
  currentIdentity.current = identity;
  const previousSource = useRef(sourceIdentity);
  const previousSnapshot = useRef(snapshot);
  const previousIdentity = useRef(identity);
  const previousWorkId = useRef(work.id);
  const [snapshotWarning, setSnapshotWarning] = useState(false);
  const questionsRef = useRef(questions); questionsRef.current = questions;
  const pinnedRef = useRef(pinned); pinnedRef.current = pinned;
  const submitted = useRef<{ questions: string; pinned: number[] } | null>(null);
  const operation = useWorkOperation(work, fresh => {
    if (submitted.current && questionsRef.current === submitted.current.questions &&
        JSON.stringify(pinnedRef.current) === JSON.stringify(submitted.current.pinned)) {
      baseline.current = submitted.current.questions;
      setPinned([]); setSelectedSources([]); setChecked(false); setSnapshotWarning(false);
      onDirtyChange?.(false);
    }
    submitted.current = null;
    onSaved(fresh);
  }, onOpenDraft);
  const dirty = questions !== baseline.current || pinned.length > 0;
  const isCurrent = (expected: string) => mounted.current && currentIdentity.current === expected;
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (previousIdentity.current === identity) return;
    previousIdentity.current = identity;
    setBusy(null);
    if (previousWorkId.current !== work.id) {
      previousWorkId.current = work.id; searchVersion.current += 1;
      const incoming = work.evidencias?.perguntas.join("\n") || "";
      baseline.current = incoming; setQuestions(incoming); setQuery(""); setHits([]);
      setPinned([]); setSelectedSources([]); setSource(null); setChecked(false);
      setError(null); setMessage(""); setSnapshotWarning(false);
      previousSource.current = sourceIdentity;
      previousSnapshot.current = snapshot;
    }
  }, [identity, work.id, work.evidencias?.perguntas, sourceIdentity, snapshot]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; searchVersion.current += 1; };
  }, [work.id]);
  useEffect(() => {
    if (previousSnapshot.current !== snapshot) {
      previousSnapshot.current = snapshot;
      setChecked(false);
    }
    if (previousSource.current !== sourceIdentity) {
      previousSource.current = sourceIdentity; searchVersion.current += 1;
      setHits([]); setPinned([]); setSelectedSources([]); setChecked(false);
      setSnapshotWarning(questions !== baseline.current);
    }
    const incoming = work.evidencias?.perguntas.join("\n") || "";
    if (!dirty && incoming !== baseline.current) { baseline.current = incoming; setQuestions(incoming); }
  }, [snapshot, sourceIdentity, work.evidencias?.perguntas, dirty, questions]);
  const evidence = work.evidencias;
  const stale = work.evidencias_atuais === false;
  async function act(name: string, action: () => Promise<void>) {
    if (busy || disabled) return; setBusy(name); setError(null); setMessage("");
    const expected = currentIdentity.current;
    try { await action(); } catch (err) { if (isCurrent(expected)) setError(humanError(err, "Não foi possível concluir a etapa")); }
    finally { if (isCurrent(expected)) setBusy(null); }
  }
  function open(id: number) { const found = evidence?.citations.find(item => item.chunk_id === id); if (found) setSource(found); }
  return <section id="work-evidence" tabIndex={-1} className="legalWorkStage workStageAnchor" aria-label="Evidências e minuta">
    <h3>Fontes e análise do contexto</h3>
    <p>Busque nos documentos originais, fixe fontes relevantes e confira a análise antes de redigir.</p>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {operation.error ? <p role="alert" className="officeError">{humanError(operation.error, "A operação falhou")}</p> : null}
    {operation.job?.status === "queued" || operation.job?.status === "running" ?
      <p role="status">{operation.job.acao === "analise" ? "Análise" : "Minuta"} em andamento. Pode sair desta página; o trabalho será retomado aqui.</p> : null}
    {operation.job?.status === "failed" ? <p role="status">A operação falhou. Revise os dados e tente novamente.</p> : null}
    {message ? <p role="status">{message}</p> : null}
    {stale ? <p role="alert">Revisão necessária. {work.motivo_revisao}</p> : null}
    {snapshotWarning ? <p role="status">As fontes mudaram. Suas perguntas foram preservadas; confira o novo inventário antes de preparar novamente.</p> : null}
    <div className="officeForm"><label>Pontos que precisam ser respondidos<textarea rows={3} value={questions} disabled={disabled || Boolean(busy)}
      onChange={e => setQuestions(e.target.value)} placeholder="Uma pergunta por linha. Ex.: Há prova de pagamento?" /></label>
      <label>Buscar no texto original<input maxLength={500} value={query} disabled={disabled} onChange={e => { searchVersion.current += 1; setQuery(e.target.value); setHits([]); }} /></label>
      <LoadingButton loading={busy === "search"} disabled={disabled || Boolean(busy) || !query.trim()} onClick={() => void act("search", async () => {
        const expected = currentIdentity.current;
        const version = ++searchVersion.current;
        const result = await buscarFontesTrabalho(work, query);
        if (isCurrent(expected) && version === searchVersion.current) setHits(result.items);
      })}>Buscar fontes</LoadingButton>
      {selectedSources.length ? <div><h4>Fontes fixadas para a análise ({selectedSources.length})</h4>
        {selectedSources.map(item => <p key={item.chunk_id}>{item.nome || `Documento ${item.documento_id}`} · p. {item.pagina} <button type="button" className="toolbarButton compact" disabled={disabled || Boolean(busy)} onClick={() => { setPinned(values => values.filter(id => id !== item.chunk_id)); setSelectedSources(values => values.filter(value => value.chunk_id !== item.chunk_id)); }}>Remover fonte</button></p>)}
      </div> : null}
      {hits.map(hit => <article className="legalEvidenceQuote" key={hit.chunk_id}><p>{hit.quote}</p><div className="officeToolbar">
        <button className="toolbarButton compact" onClick={() => setSource(hit)}>{hit.nome || `Documento ${hit.documento_id}`} · p. {hit.pagina}</button>
        <label className="officeCheckbox"><input type="checkbox" checked={pinned.includes(hit.chunk_id)} disabled={disabled || Boolean(busy)}
          onChange={e => { setPinned(values => e.target.checked ? [...values, hit.chunk_id] : values.filter(id => id !== hit.chunk_id)); setSelectedSources(values => e.target.checked ? [...values.filter(item => item.chunk_id !== hit.chunk_id), hit] : values.filter(item => item.chunk_id !== hit.chunk_id)); }} /> Usar esta fonte na análise</label></div></article>)}
      {!work.escopo ? <p role="status">Registre o escopo dos documentos na etapa anterior para preparar a análise.</p> : null}
      <LoadingButton loading={busy === "prepare"} disabled={disabled || Boolean(busy) || operation.working || !work.escopo} onClick={() => void act("prepare", async () => {
        submitted.current = { questions, pinned: [...pinned] };
        await operation.start("analise", questions.split("\n").filter(line => line.trim()), pinned);
      })}>{operation.job?.status === "failed" && operation.job.acao === "analise" ? "Tentar análise novamente" :
        evidence ? "Atualizar análise das evidências" : "Preparar análise das evidências"}</LoadingButton>
    </div>
    <p className="officeHint">Relatos e instruções do advogado são informações a conferir nas fontes, não prova documentada.</p>
    {evidence ? <>
      <details><summary>Inventário do contexto ({evidence.inventario?.length || 0} versões)</summary>
        <p>O índice descreve peças. O inventário inclui todas as versões do contexto; o texto das versões com extração pendente ou falha ainda não entra na análise.</p>
        {evidence.inventario?.map(item => <p key={item.documento_arquivo_id}>{item.nome || `Documento #${item.documento_id}`} · versão #{item.documento_arquivo_id} · {item.paginas ?? "?"} páginas · {item.extraction_status === "complete" ? "texto extraído" : `extração ${item.extraction_status}`}</p>)}
      </details>
      <p className="officeHint">Análise proposta para revisão. Uma referência existente não certifica que a conclusão está correta.</p>
      {([ ["Fatos e alegações", evidence.analise.fatos], ["Cronologia", evidence.analise.cronologia], ["Contradições e prova contrária", evidence.analise.contradicoes] ] as const).map(([title, facts]) =>
        <section key={title}><h4>{title}</h4>{facts.length ? facts.map((fact, index) => <article className="legalEvidenceQuote" key={index}><p>{fact.texto}</p><small>{fact.natureza.replaceAll("_", " ")}</small>
          <div className="officeToolbar">{fact.fontes.map(id => <button key={id} className="toolbarButton compact" onClick={() => open(id)}>Conferir fonte {evidence.citations.find(c => c.chunk_id === id)?.pagina ? `· p. ${evidence.citations.find(c => c.chunk_id === id)?.pagina}` : ""}</button>)}</div></article>) : <p>Nenhum ponto identificado pela análise; confira o acervo.</p>}</section>)}
      <h4>Lacunas e documentos necessários</h4>
      {evidence.analise.lacunas.map((gap, index) => <article className="legalEvidenceQuote" key={index}><p>{gap}</p>
        <button className="toolbarButton compact" disabled={disabled || Boolean(busy)}
          onClick={() => void act(`task-${index}`, async () => {
            const expected = currentIdentity.current;
            const task = await criarPendenciaTrabalho(work, index);
            if (isCurrent(expected)) setMessage(`Pendência #${task.id} vinculada ao trabalho em Tarefas e pendências.`);
          })}>Criar pendência documental</button></article>)}
      {evidence.avisos.map((warning, index) => <p className="officeHint" key={index}>{warning}</p>)}
      {!evidence.conferida ? <><label className="officeCheckbox"><input type="checkbox" checked={checked} disabled={disabled || Boolean(busy)} onChange={e => setChecked(e.target.checked)} /> Conferi as fontes, os pontos contrários e as lacunas desta análise.</label>
        <LoadingButton loading={busy === "review"} disabled={disabled || Boolean(busy) || operation.working || !checked || stale || dirty} onClick={() => void act("review", async () => { const expected = currentIdentity.current; const result = await conferirEvidencias(work); if (isCurrent(expected)) onSaved(result); })}>Registrar conferência</LoadingButton></> : <p role="status">Conferência registrada. Lacunas documentais continuam exigindo acompanhamento.</p>}
      <h3 id="work-draft" tabIndex={-1} className="workStageAnchor">3. Minuta e revisão</h3>
      <LoadingButton loading={busy === "draft"} disabled={disabled || Boolean(busy) || operation.working || !canDraft || !evidence.conferida || stale || dirty} onClick={() => void act("draft", async () => {
        await operation.start("minuta");
      })}>{operation.job?.status === "failed" && operation.job.acao === "minuta" ? "Tentar minuta novamente" :
        work.peticao_id ? "Gerar nova versão da minuta" : "Gerar minuta para revisão"}</LoadingButton>
    </> : null}
    {source ? <DocumentEvidenceDialog documentoId={source.documento_id} nome={source.nome || `Documento ${source.documento_id}`} versaoId={source.documento_arquivo_id} pagina={source.pagina} onClose={() => setSource(null)} /> : null}
  </section>;
}
