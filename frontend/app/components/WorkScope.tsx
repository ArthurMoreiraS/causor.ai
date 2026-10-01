"use client";
import { useEffect, useRef, useState } from "react";
import { listarDocumentos, type DocumentoBiblioteca } from "@/lib/api";
import { salvarEscopo, type DocumentoEscopo, type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
import { LoadingButton } from "./ui";
import DocumentEvidenceDialog from "./DocumentEvidenceDialog";

function scopeFields(scope: Trabalho["escopo"]) {
  return JSON.stringify({ data_referencia: scope?.data_referencia || "", declaracao: scope?.declaracao || "", documentos: scope?.documentos || [] });
}

export default function WorkScope({ work, disabled, onSaved, onDirtyChange }: { work: Trabalho; disabled: boolean; onSaved: (value: Trabalho) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const [date, setDate] = useState(work.escopo?.data_referencia || "");
  const [declaration, setDeclaration] = useState(work.escopo?.declaracao || "");
  const [entries, setEntries] = useState<DocumentoEscopo[]>(work.escopo?.documentos || []);
  const [documents, setDocuments] = useState<DocumentoBiblioteca[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageSource, setPageSource] = useState<{ doc: number; version: number; page: number; name: string } | null>(null);
  const baseline = useRef(scopeFields(work.escopo));
  const workIdentity = `${work.id}:${work.versao}`;
  const currentIdentity = useRef(workIdentity);
  currentIdentity.current = workIdentity;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { setBusy(false); }, [workIdentity]);
  const snapshot = scopeFields({ data_referencia: date, declaracao: declaration, documentos: entries });
  const dirty = snapshot !== baseline.current;
  const [conflict, setConflict] = useState(false);
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    const incoming = scopeFields(work.escopo);
    if (incoming === baseline.current) return;
    if (dirty) { setConflict(true); return; }
    baseline.current = incoming;
    setDate(work.escopo?.data_referencia || ""); setDeclaration(work.escopo?.declaracao || "");
    setEntries(work.escopo?.documentos || []); setConflict(false);
  }, [work.escopo, dirty]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const reload = () => listarDocumentos({ processo_id: work.processo_id || undefined, limit: 50, offset }).then(result => {
      if (active) {
        setDocuments(result.items); setTotal(result.total);
        if (result.items.some(doc => doc.versao && !["complete", "failed", "unsupported_mime"].includes(doc.versao.extracao))) timer = setTimeout(reload, 3000);
      }
    }).catch(err => { if (active) setError(humanError(err, "Falha ao consultar o acervo")); });
    void reload();
    return () => { active = false; clearTimeout(timer); };
  }, [work.processo_id, offset]);
  function changeEntry(id: number, transform: (entry: DocumentoEscopo) => DocumentoEscopo) {
    setEntries(values => {
      const current = values.find(v => v.versao_id === id) || { versao_id: id, origem: "autos_enviados" as const, pecas: [] };
      return [...values.filter(v => v.versao_id !== id), transform(current)];
    });
  }
  async function save() {
    if (busy || disabled) return; setBusy(true); setError(null);
    const expected = currentIdentity.current;
    try {
      const result = await salvarEscopo(work, { data_referencia: date, declaracao: declaration, documentos: entries });
      if (!mounted.current || currentIdentity.current !== expected) return;
      baseline.current = scopeFields(result.escopo);
      setDate(result.escopo?.data_referencia || "");
      setDeclaration(result.escopo?.declaracao || "");
      setEntries(result.escopo?.documentos || []);
      setConflict(false); onDirtyChange?.(false); onSaved(result);
    }
    catch (err) { if (mounted.current && currentIdentity.current === expected) setError(humanError(err, "Não foi possível registrar o escopo")); }
    finally { if (mounted.current && currentIdentity.current === expected) setBusy(false); }
  }
  return <details className="legalWorkStage"><summary>Declarar o acervo e identificar peças dentro dos PDFs</summary>
    <p>Registre até quando os documentos foram conferidos e o que pode estar faltando. A declaração não equivale à conferência no tribunal.</p>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {conflict ? <p role="alert">O escopo foi alterado em outra sessão. Copie suas alterações antes de recarregar e confira a versão.</p> : null}
    <p className="officeHint">O índice descreve peças e origem. A análise considera todo o acervo processado do processo, inclusive provas contrárias não listadas aqui.</p>
    {entries.filter(item => !documents.some(doc => doc.versao?.id === item.versao_id)).map(item =>
      <p className="officeHint" key={item.versao_id}>Referência do índice à versão #{item.versao_id}: não está entre as versões atuais desta página. Pode ser histórica; confira no acervo.</p>)}
    <div className="officeForm"><label>Data de referência do acervo<input type="date" required value={date} disabled={disabled || busy} onChange={e => setDate(e.target.value)} /></label>
      <label>Declaração de cobertura e limitações<textarea required minLength={20} maxLength={3000} rows={3} value={declaration} disabled={disabled || busy} onChange={e => setDeclaration(e.target.value)} /></label></div>
    {documents.map(doc => {
      const version = doc.versao; if (!version) return <p key={doc.id}>{doc.nome}: sem versão recebida.</p>;
      const entry = entries.find(item => item.versao_id === version.id);
      return <article key={version.id} className="legalEvidenceQuote officeForm"><h4>{doc.nome}</h4>
        <p>{version.paginas ?? "?"} páginas · {version.extracao === "complete" ? "Texto extraído" : version.extracao === "failed" ? "Falha de extração; confira o arquivo e reprocese" : "Processamento pendente"} · {doc.no_contexto ? "No conjunto atual" : "Fora do conjunto atual"}</p>
        {version.paginas_diagnostico?.length ? <details><summary>Conferir extração por página</summary>
          <p>Páginas processadas são preservadas. Ao reprocessar documentos com falha, o OCR retoma somente as páginas pendentes.</p>
          {version.paginas_diagnostico.map(p => <p key={p.page}><button className="toolbarButton compact" onClick={() => setPageSource({ doc: doc.id, version: version.id, page: p.page, name: doc.nome })}>Página {p.page}</button> · {p.status === "failed" ? p.error : `${p.ocr ? "OCR" : "Texto nativo"} · ${p.chars} caracteres`}</p>)}
        </details> : null}
        <label>Origem informada<select value={entry?.origem || ""} disabled={disabled || busy} onChange={e => { if (e.target.value) changeEntry(version.id, old => ({ ...old, origem: e.target.value as DocumentoEscopo["origem"] })); }}>
          <option value="">Não informada</option><option value="autos_enviados">Autos enviados pelo advogado</option><option value="subsidio_cliente">Documento do cliente</option><option value="fonte_externa">Fonte externa identificada na declaração</option></select></label>
        {entry?.pecas.map((piece, index) => <div className="legalWorkFields" key={index}>
          <label>Nome da peça<input value={piece.nome} required disabled={disabled || busy} onChange={e => changeEntry(version.id, old => ({ ...old, pecas: old.pecas.map((p, i) => i === index ? { ...p, nome: e.target.value } : p) }))} /></label>
          <div className="legalWorkFields"><label>Página inicial<input type="number" min={1} max={version.paginas || undefined} value={piece.pagina_inicio} disabled={disabled || busy} onChange={e => changeEntry(version.id, old => ({ ...old, pecas: old.pecas.map((p, i) => i === index ? { ...p, pagina_inicio: Number(e.target.value) } : p) }))} /></label>
            <label>Página final<input type="number" min={1} max={version.paginas || undefined} value={piece.pagina_fim} disabled={disabled || busy} onChange={e => changeEntry(version.id, old => ({ ...old, pecas: old.pecas.map((p, i) => i === index ? { ...p, pagina_fim: Number(e.target.value) } : p) }))} /></label></div>
          <button className="toolbarButton compact" disabled={disabled || busy} onClick={() => changeEntry(version.id, old => ({ ...old, pecas: old.pecas.filter((_, i) => i !== index) }))}>Remover do índice</button>
        </div>)}
        <button className="toolbarButton compact" disabled={disabled || busy || !version.paginas} onClick={() => changeEntry(version.id, old => ({ ...old, pecas: [...old.pecas, { nome: "", pagina_inicio: 1, pagina_fim: 1 }] }))}>Identificar peça no PDF</button>
      </article>;
    })}
    <div className="tablePager"><button className="toolbarButton" disabled={!offset || busy} onClick={() => setOffset(v => Math.max(0, v - 50))}>Documentos anteriores</button>
      <span>{total} documentos</span><button className="toolbarButton" disabled={offset + 50 >= total || busy} onClick={() => setOffset(v => v + 50)}>Mais documentos</button></div>
    <LoadingButton loading={busy} disabled={disabled || !date || declaration.trim().length < 20} onClick={() => void save()}>Registrar escopo e índice</LoadingButton>
    <p className="officeHint">Alterar o escopo exige preparar e conferir novamente as evidências. O PDF original e suas páginas são preservados.</p>
    {pageSource ? <DocumentEvidenceDialog documentoId={pageSource.doc} nome={pageSource.name} versaoId={pageSource.version} pagina={pageSource.page} onClose={() => setPageSource(null)} /> : null}
  </details>;
}
