"use client";
import { useEffect, useState } from "react";
import { baixarFonteCitada, listarTrechosDocumento, listarVersoesDocumento, type DocumentoTrechos, type DocumentoVersao } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { Modal } from "./ui";

export function documentStatus(extraction?: string, summary?: string): string {
  if (extraction === "failed" || summary === "failed") return "Falha no processamento";
  if (extraction === "unsupported_mime") return "Formato sem extração de texto";
  if (extraction === "complete" && summary === "complete") return "Texto e resumo disponíveis";
  if (extraction === "complete") return "Texto extraído; aguardando resumo";
  return "Aguardando extração";
}

export default function DocumentEvidenceDialog({ documentoId, nome, versaoId, pagina = 1, onClose }: {
  documentoId: number; nome: string; versaoId?: number; pagina?: number; onClose: () => void;
}) {
  const [versions, setVersions] = useState<DocumentoVersao[]>([]);
  const [versionTotal, setVersionTotal] = useState(0);
  const [version, setVersion] = useState<number | undefined>(versaoId);
  const [page, setPage] = useState(pagina);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<DocumentoTrechos | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [moreBusy, setMoreBusy] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    listarVersoesDocumento(documentoId).then(result => {
      if (active) { setVersions(result.items); setVersionTotal(result.total); setVersion(v => v || result.items[0]?.id); if (!result.items.length) setLoading(false); }
    }).catch(err => { if (active) { setError(humanError(err, "Falha ao carregar versões")); setLoading(false); } });
    return () => { active = false; };
  }, [documentoId, tick]);
  useEffect(() => {
    if (!version) return;
    let active = true;
    setLoading(true); setData(null);
    const timer = setTimeout(() => {
      listarTrechosDocumento(documentoId, version, query, offset).then(result => {
        if (active) { setData(result); setError(null); }
      }).catch(err => { if (active) setError(humanError(err, "Falha ao carregar evidências")); })
        .finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [documentoId, version, query, offset, tick]);
  useEffect(() => {
    if (!version) return;
    let active = true, url: string | null = null;
    setBlobUrl(null); setPdfError(null);
    baixarFonteCitada(documentoId, version).then(blob => {
      if (blob.type !== "application/pdf") throw new Error("A visualização está disponível somente para PDFs.");
      if (active) { url = URL.createObjectURL(blob); setBlobUrl(url); }
    }).catch(err => { if (active) setPdfError(humanError(err, "Falha ao abrir o PDF")); });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [documentoId, version, tick]);
  async function moreVersions() {
    setMoreBusy(true);
    try { const result = await listarVersoesDocumento(documentoId, versions.length); setVersions(v => [...v, ...result.items]); setVersionTotal(result.total); }
    catch (err) { setError(humanError(err, "Falha ao carregar versões anteriores")); }
    finally { setMoreBusy(false); }
  }
  return <Modal className="evidenceDialog" labelledBy="document-evidence-title" onClose={onClose}>
    <header className="officeHead"><div><h2 id="document-evidence-title">{nome}</h2><p>Confira o resumo, os trechos e o PDF da mesma versão.</p></div>
      <button className="toolbarButton" onClick={onClose}>Fechar</button></header>
    <div className="officeToolbar"><label>Versão<select value={version || ""} onChange={e => { setVersion(Number(e.target.value)); setOffset(0); setPage(1); }}>
      {version && !versions.some(v => v.id === version) ? <option value={version}>Versão citada #{version}</option> : null}
      {versions.map(v => <option key={v.id} value={v.id}>{new Date(v.created_at).toLocaleString("pt-BR")} · {v.atual ? "atual" : "anterior"} · {v.sha256.slice(0, 8)}</option>)}
    </select></label>
      {versions.length < versionTotal ? <button className="toolbarButton" disabled={moreBusy} onClick={() => void moreVersions()}>Mais versões</button> : null}
      <button className="toolbarButton" onClick={() => setTick(v => v + 1)} disabled={loading}>Atualizar evidências</button></div>
    {error ? <p className="officeError" role="alert">{error}</p> : null}
    {!version && !loading && !error ? <p>Este registro ainda não tem um arquivo verificado.</p> : null}
    <div className="evidenceColumns"><section className="evidenceText">
      {data ? <><p className="officeHint">{documentStatus(data.versao.extracao, data.versao.resumo_status)} · {data.versao.paginas ?? "—"} páginas</p>
        {data.resumo ? <details open><summary>Resumo com apoio nos documentos</summary><p className="officeDescription">{data.resumo}</p>
          {(data.citations || []).map((c, i) => <p key={i} className="officeDescription">{c.quote} {c.pagina ? <button className="toolbarButton compact" onClick={() => setPage(c.pagina!)}>Página {c.pagina}</button> : null}</p>)}
        </details> : null}</> : null}
      <div className="officeToolbar"><label>Buscar no texto extraído<input value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }} /></label></div>
      {loading ? <p role="status">Carregando evidências…</p> : null}
      {data?.items.map(chunk => <article key={chunk.id} className="evidenceChunk"><button className="toolbarButton compact" onClick={() => setPage(chunk.pagina)}>Página {chunk.pagina}{chunk.ocr ? " · OCR" : ""}</button><p className="officeDescription">{chunk.texto}</p></article>)}
      {data && !data.items.length ? <p className="officeHint">{query ? "Nenhum trecho corresponde à busca." : "O texto extraído ficará disponível após o processamento."}</p> : null}
      <footer className="officePagination"><span>{data?.total ?? 0} trechos</span>
        <button className="toolbarButton compact" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Anteriores</button>
        <button className="toolbarButton compact" disabled={loading || offset + 20 >= (data?.total || 0)} onClick={() => setOffset(offset + 20)}>Próximos</button></footer>
    </section><section className="evidencePdf">
      {pdfError ? <p role="alert" className="officeError">{pdfError}</p> : null}
      {blobUrl ? <><a className="toolbarButton" href={`${blobUrl}#page=${page}`} target="_blank" rel="noreferrer">Abrir PDF em outra aba · página {page}</a>
        <iframe title={`PDF de ${nome}`} src={`${blobUrl}#page=${page}`} /></> : version && !pdfError ? <p role="status">Carregando PDF…</p> : null}
    </section></div>
  </Modal>;
}
