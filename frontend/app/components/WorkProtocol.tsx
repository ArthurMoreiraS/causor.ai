"use client";
import { useEffect, useState } from "react";
import { listarDocumentos, type DocumentoBiblioteca, type Processo } from "@/lib/api";
import { type Trabalho } from "@/lib/work-api";
import { aprovarPacote, baixarArquivoTrabalho, cancelarTentativa, conferirComprovante, criarPacote, informarEnvio,
  iniciarEnvioExterno, listarPacotes, listarTentativas, receberComprovante, type AnexoPacote, type Pacote, type Tentativa } from "@/lib/package-api";
import { humanError } from "@/lib/errors";
import { LoadingButton } from "./ui";

const STATUS: Record<string, string> = { aguardando_envio_externo: "Aguardando envio pelo advogado", envio_informado: "Envio informado — comprovante ainda não conferido",
  envio_confirmado: "Envio confirmado por conferência humana", resultado_incerto: "Resultado incerto — conferir antes de repetir", cancelado: "Tentativa cancelada", falha_confirmada: "Falha confirmada" };

export default function WorkProtocol({ work, processo, disabled, refreshKey = 0, onChanged }: {
  work: Trabalho; processo?: Processo; disabled: boolean; refreshKey?: number; onChanged: () => void;
}) {
  const [packages, setPackages] = useState<Pacote[]>([]);
  const [attempts, setAttempts] = useState<Tentativa[]>([]);
  const [documents, setDocuments] = useState<DocumentoBiblioteca[]>([]);
  const [offset, setOffset] = useState(0), [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<AnexoPacote[]>([]);
  const [court, setCourt] = useState(processo?.tribunal || "");
  const [destination, setDestination] = useState(processo?.orgao_julgador || "");
  const [actType, setActType] = useState(work.providencia);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState<string | null>(null), [error, setError] = useState<string | null>(null);
  const [protocol, setProtocol] = useState(""), [date, setDate] = useState("");
  const [notes, setNotes] = useState(""), [receiptChecked, setReceiptChecked] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [tick, setTick] = useState(0);
  const package_ = packages[0];
  const attempt = attempts.find(a => !["cancelado", "falha_confirmada"].includes(a.status));
  const receipt = attempt?.comprovantes[0];
  const closed = attempt?.status === "envio_confirmado";
  useEffect(() => {
    let active = true;
    listarPacotes(work).then(result => { if (active) { setPackages(result.items); setChecked(false); } })
      .catch(err => { if (active) setError(humanError(err, "Falha ao consultar pacotes")); });
    return () => { active = false; };
  }, [work, tick, refreshKey]);
  useEffect(() => {
    let active = true;
    if (!package_) { setAttempts([]); return; }
    listarTentativas(package_).then(result => { if (active) setAttempts(result.items); })
      .catch(err => { if (active) setError(humanError(err, "Falha ao consultar tentativas")); });
    return () => { active = false; };
  }, [package_, tick]);
  useEffect(() => {
    let active = true;
    listarDocumentos({ processo_id: work.processo_id || undefined, limit: 50, offset }).then(result => {
      if (active) { setDocuments(result.items); setTotal(result.total); }
    }).catch(err => { if (active) setError(humanError(err, "Falha ao consultar anexos")); });
    return () => { active = false; };
  }, [work.processo_id, offset, refreshKey]);
  async function run(name: string, action: () => Promise<void>) {
    if (busy || disabled) return; setBusy(name); setError(null);
    try { await action(); } catch (err) { setError(humanError(err, "Não foi possível concluir a etapa")); }
    finally { setBusy(null); }
  }
  function storeAttempt(value: Tentativa) { setAttempts(items => [value, ...items.filter(i => i.id !== value.id)]); setReceiptChecked(false); onChanged(); }
  function move(index: number, delta: number) { setSelected(items => {
    const next = [...items], target = index + delta;
    if (target < 0 || target >= next.length) return items;
    [next[index], next[target]] = [next[target], next[index]]; return next;
  }); }

  return <section id="work-package" tabIndex={-1} className="legalWorkStage workStageAnchor" aria-label="Pacote e protocolo">
    <h3>5. Pacote e acompanhamento do protocolo</h3>
    <p>Prepare e aprove os arquivos. O envio no tribunal será realizado por você. Não é necessário conectar o executor.</p>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {!attempt ? <details open={!package_}><summary>Montar uma versão do pacote</summary>
      <div className="officeForm"><label>Tribunal de destino<input value={court} maxLength={50} disabled={disabled || Boolean(busy)} onChange={e => setCourt(e.target.value.toUpperCase())} /></label>
        <label>Órgão de destino<input value={destination} maxLength={255} disabled={disabled || Boolean(busy)} onChange={e => setDestination(e.target.value)} /></label>
        <label>Tipo de ato<input value={actType} maxLength={100} disabled={disabled || Boolean(busy)} onChange={e => setActType(e.target.value)} /></label>
        <p>Instância revisada: {work.grau}º grau. Limites específicos do tribunal precisam ser conferidos no destino.</p></div>
      <h4>Escolher anexos</h4>
      {documents.map(doc => <label className="legalAttachment" key={doc.id}><input type="checkbox" disabled={disabled || Boolean(busy) || !doc.no_contexto || !doc.versao}
        checked={selected.some(a => a.versao_id === doc.versao?.id)} onChange={e => { const id = doc.versao!.id; setSelected(values => e.target.checked ? [...values, { versao_id: id, nome: doc.nome }] : values.filter(a => a.versao_id !== id)); }} />
        {doc.nome}{!doc.no_contexto ? " — fora do contexto atual" : ""}</label>)}
      <div className="tablePager"><button className="toolbarButton" disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 50))}>Anteriores</button><span>{total} documentos</span>
        <button className="toolbarButton" disabled={offset + 50 >= total} onClick={() => setOffset(v => v + 50)}>Mais documentos</button></div>
      {selected.map((item, index) => <div className="officeToolbar" key={item.versao_id}><label>Anexo {index + 1}<input value={item.nome} maxLength={180} disabled={disabled || Boolean(busy)} onChange={e => setSelected(values => values.map(a => a.versao_id === item.versao_id ? { ...a, nome: e.target.value } : a))} /></label>
        <button className="toolbarButton compact" disabled={index === 0 || Boolean(busy)} onClick={() => move(index, -1)}>Subir</button><button className="toolbarButton compact" disabled={index === selected.length - 1 || Boolean(busy)} onClick={() => move(index, 1)}>Descer</button></div>)}
      <LoadingButton loading={busy === "build"} disabled={disabled || Boolean(busy) || !court.trim() || !destination.trim() || !actType.trim()}
        onClick={() => void run("build", async () => { await criarPacote(work, { tribunal: court, orgao: destination, tipo_ato: actType, grau: work.grau as "1" | "2", sistema: processo?.sistema }, selected); setTick(v => v + 1); })}>Preparar pacote para conferência</LoadingButton>
    </details> : null}
    {package_ ? <>
      <h4>Pacote versão {package_.versao}</h4><p>{package_.destino.numero_processo} · {package_.destino.tribunal} · {package_.destino.grau}º grau · {package_.destino.orgao}</p>
      {!package_.atual ? <p role="alert">{package_.motivo}</p> : null}
      {package_.items.map((item, index) => <div className="officeToolbar" key={index}><span>{item.nome} · {Math.ceil(item.size_bytes / 1024)} KB</span>
        <button className="toolbarButton compact" disabled={disabled || Boolean(busy)} onClick={() => void run(`file-${index}`, () => baixarArquivoTrabalho(`/pacotes/${package_.id}/arquivos/${index}`, item.nome))}>Baixar para conferir</button></div>)}
      {!package_.aprovada_em ? <><label><input type="checkbox" checked={checked} disabled={disabled || Boolean(busy) || !package_.atual} onChange={e => setChecked(e.target.checked)} /> Conferi petição, anexos, ordem e destino desta versão.</label>
        <LoadingButton loading={busy === "approve"} disabled={disabled || Boolean(busy) || !checked || !package_.atual} onClick={() => void run("approve", async () => { await aprovarPacote(package_); setTick(v => v + 1); onChanged(); })}>Aprovar este pacote</LoadingButton></> : <p>Versão aprovada em {new Date(package_.aprovada_em).toLocaleString("pt-BR")}.</p>}
      <LoadingButton loading={busy === "zip"} disabled={disabled || Boolean(busy) || !package_.aprovada_em || !package_.atual} onClick={() => void run("zip", () => baixarArquivoTrabalho(`/pacotes/${package_.id}/exportar`, `pacote-${package_.id}.zip`))}>Baixar pacote aprovado</LoadingButton>
      <p className="officeHint">O índice do ZIP serve para conferência. Não o anexe ao tribunal automaticamente. Baixar não registra protocolo.</p>
      {!attempt ? <LoadingButton loading={busy === "start"} disabled={disabled || Boolean(busy) || !package_.aprovada_em || !package_.atual} onClick={() => void run("start", async () => storeAttempt(await iniciarEnvioExterno(package_, crypto.randomUUID())))}>Acompanhar envio externo</LoadingButton> : <>
        <h4>{STATUS[attempt.status] || attempt.status}</h4>
        {!closed ? <div className="officeForm">
          <label>Número do protocolo informado<input value={protocol} maxLength={150} disabled={disabled || Boolean(busy)} onChange={e => setProtocol(e.target.value)} /></label>
          <label>Data e hora do ato<input type="datetime-local" value={date} disabled={disabled || Boolean(busy)} onChange={e => setDate(e.target.value)} /></label>
          <LoadingButton loading={busy === "report"} disabled={disabled || Boolean(busy) || !protocol.trim() || !date}
            onClick={() => void run("report", async () => storeAttempt(await informarEnvio(attempt, protocol, new Date(date).toISOString())))}>Registrar envio informado</LoadingButton>
          <label>Comprovante PDF<input type="file" accept="application/pdf,.pdf" disabled={disabled || Boolean(busy)} onChange={e => setFile(e.target.files?.[0] || null)} /></label>
          <LoadingButton loading={busy === "receipt"} disabled={disabled || Boolean(busy) || !file}
            onClick={() => void run("receipt", async () => { storeAttempt(await receberComprovante(attempt, file!)); setFile(null); })}>Receber comprovante</LoadingButton>
        </div> : null}
        {receipt ? <article className="legalEvidenceQuote"><p>Comprovante: {receipt.nome} · {receipt.status === "conferido_advogado" ? "Conferido pelo advogado" : receipt.status === "divergente" ? "Número do processo divergente" : "Recebido; aguarda conferência"}</p>
          <button className="toolbarButton" disabled={disabled || Boolean(busy)} onClick={() => void run("receipt-download", () => baixarArquivoTrabalho(`/comprovantes/${receipt.id}/arquivo`, receipt.nome))}>Abrir arquivo do comprovante</button>
          <p>Números encontrados: {receipt.dados.numeros_extraidos.join(", ") || "Não identificados no texto; confira visualmente o PDF."}</p>
          {receipt.dados.protocolos_sugeridos?.length ? <p>Protocolo encontrado no texto (confira): {receipt.dados.protocolos_sugeridos.join(", ")}</p> : null}
          {receipt.dados.datas_sugeridas?.length ? <p>Datas encontradas no texto (confira qual corresponde ao ato): {receipt.dados.datas_sugeridas.join(", ")}</p> : null}
          {!closed ? <div className="officeForm"><label>Observações da conferência<textarea minLength={20} maxLength={3000} value={notes} disabled={disabled || Boolean(busy)} onChange={e => setNotes(e.target.value)} /></label>
            <label><input type="checkbox" checked={receiptChecked} disabled={disabled || Boolean(busy)} onChange={e => setReceiptChecked(e.target.checked)} /> Conferi processo, destino, número, data do ato e correspondência com os arquivos aprovados.</label>
            <LoadingButton loading={busy === "confirm"} disabled={disabled || Boolean(busy) || !receiptChecked || !protocol.trim() || !date || notes.trim().length < 20 || receipt.status === "divergente"}
              onClick={() => void run("confirm", async () => storeAttempt(await conferirComprovante(attempt, receipt, { numero_processo: package_.destino.numero_processo!, protocolo: protocol, data_ato: new Date(date).toISOString(), observacoes: notes })))}>Registrar conferência humana do comprovante</LoadingButton></div> : null}
        </article> : null}
        {!receipt && attempt.status === "aguardando_envio_externo" ? <details><summary>Cancelar acompanhamento antes do envio</summary><label>Motivo<input minLength={20} value={cancelReason} onChange={e => setCancelReason(e.target.value)} /></label>
          <button className="toolbarButton" disabled={disabled || Boolean(busy) || cancelReason.trim().length < 20} onClick={() => void run("cancel", async () => storeAttempt(await cancelarTentativa(attempt, cancelReason)))}>Confirmar cancelamento sem envio</button></details> : null}
      </>}
    </> : null}
  </section>;
}
