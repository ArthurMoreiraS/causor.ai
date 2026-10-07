"use client";

import { FileUp, Info, Loader2, RefreshCcw, ShieldAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  AutosStatus,
  criarOverrideContexto,
  declararGrauNaoAplicavel,
  reprocessarAutos,
  enviarAutos,
  statusAutos
} from "@/lib/api";
import { humanError } from "@/lib/errors";
import { LoadingButton } from "./ui";

export type ContextUiState =
  | "not_captured"
  | "capturing"
  | "incomplete"
  | "processing"
  | "ready"
  | "stale"
  | "blocked";

export function deriveUiState(status: AutosStatus | null): ContextUiState {
  if (status?.contexto?.ready) return "ready";
  if (status?.contexto?.missing.some((m) => m.includes("obsoleto") || m.includes("stale"))) return "stale";
  if (!status || status.instancias.length === 0) return "not_captured";
  const capturas = status.instancias.map((i) => i.captura);
  if (capturas.every((c) => c === null)) return "not_captured";
  if (capturas.some((c) => c && ["queued", "enumerating", "downloading", "verifying"].includes(c.status))) {
    return "capturing";
  }
  if (capturas.some((c) => c && ["incomplete", "failed"].includes(c.status))) return "incomplete";
  if (capturas.every((c) => c === null || c.status === "complete" || c.status === "not_applicable")) {
    if (status.contexto?.missing.some((m) => m.startsWith("instancia:") || m.includes("failed"))) return "incomplete";
    return "processing";
  }
  return "blocked";
}

const STATE_TONE: Record<ContextUiState, string> = {
  not_captured: "neutral",
  capturing: "info",
  incomplete: "warn",
  processing: "info",
  ready: "ok",
  stale: "warn",
  blocked: "risk"
};

const STATE_LABEL: Record<ContextUiState, string> = {
  not_captured: "Autos não capturados",
  capturing: "Capturando autos…",
  incomplete: "Contexto incompleto",
  processing: "Processando documentos…",
  ready: "Contexto disponível para revisão",
  stale: "Contexto desatualizado",
  blocked: "Bloqueado"
};

export default function ProcessContextStatus({ processoId, initialDegree = "1", onReceiveDocuments, receivingDisabled = false, assistedOnly = false }: {
  processoId: number; initialDegree?: "1" | "2"; onReceiveDocuments?: () => void; receivingDisabled?: boolean; assistedOnly?: boolean;
}) {
  const [status, setStatus] = useState<AutosStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [justification, setJustification] = useState("");
  const [overrideOk, setOverrideOk] = useState(false);
  const [grau, setGrau] = useState(initialDegree);
  useEffect(() => { setGrau(initialDegree); }, [initialDegree, processoId]);
  const [absence, setAbsence] = useState("");
  const requestEpoch = useRef(0);
  const inFlight = useRef(false);
  const pendingReload = useRef(false);

  async function reload() {
    if (inFlight.current) { pendingReload.current = true; return; }
    inFlight.current = true;
    const epoch = requestEpoch.current;
    try {
      const result = await statusAutos(processoId);
      if (epoch !== requestEpoch.current) return;
      setStatus(result);
      setError(null);
    } catch (err) {
      if (epoch === requestEpoch.current) setError(humanError(err, "Falha ao carregar status dos autos"));
    } finally {
      if (epoch === requestEpoch.current) {
        setLoading(false); inFlight.current = false;
        if (pendingReload.current) { pendingReload.current = false; void reload(); }
      }
    }
  }

  useEffect(() => {
    requestEpoch.current += 1; inFlight.current = false; pendingReload.current = false;
    setLoading(true); setStatus(null);
    void reload();
    const timer = window.setInterval(() => void reload(), 5000);
    return () => { requestEpoch.current += 1; inFlight.current = false; pendingReload.current = false; window.clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processoId]);

  // O advogado já tem acesso aos autos: deixar que ele entregue resolve o caso
  // em que nenhum canal automático alcança o tribunal.
  async function enviar(arquivos: FileList | null) {
    if (!arquivos || arquivos.length === 0) return;
    setBusy("upload");
    try {
      await enviarAutos(processoId, Array.from(arquivos), grau);
      await reload();
    } catch (err) {
      setError(humanError(err, "Falha ao enviar os autos"));
    } finally {
      setBusy(null);
    }
  }

  async function liberar() {
    setBusy("override");
    try {
      await criarOverrideContexto(processoId, "draft", justification);
      setOverrideOk(true);
      setShowOverride(false);
    } catch (err) {
      setError(humanError(err, "Falha ao registrar liberação"));
    } finally {
      setBusy(null);
    }
  }

  async function declararAusencia() {
    setBusy("ausencia");
    try {
      await declararGrauNaoAplicavel(processoId, grau, absence);
      setAbsence("");
      await reload();
    } catch (err) {
      setError(humanError(err, "Falha ao registrar declaração"));
    } finally { setBusy(null); }
  }

  async function reprocessar() {
    setBusy("processar");
    try { await reprocessarAutos(processoId); await reload(); }
    catch (err) { setError(humanError(err, "Falha ao retomar processamento")); }
    finally { setBusy(null); }
  }

  if (loading) {
    return (
      <section className="contextStatus contextLoading">
        <Loader2 className="spin" size={14} /> Carregando autos do processo…
      </section>
    );
  }

  const uiState = deriveUiState(status);
  const blocked = uiState !== "ready";
  const pendentes =
    status?.instancias.reduce((total, instancia) => {
      const captura = instancia.captura;
      if (!captura) return total;
      return total + Math.max(captura.expected_count - captura.captured_count, 0);
    }, 0) ?? 0;

  const contexto = status?.contexto;
  const capturadas = status?.instancias.filter((instancia) => instancia.captura) ?? [];

  return (
    <section className="contextStatus">
      <header className="contextHead">
        <div className="contextTitle">
          <h3>Autos do processo</h3>
          <span className={`statusBadge ${STATE_TONE[uiState]}`}>{STATE_LABEL[uiState]}</span>
        </div>
        <div className="contextHeadActions">
          <div className="segmented" role="group" aria-label="Grau dos autos">
            {(["1", "2"] as const).map((value) => (
              <button key={value} type="button" aria-pressed={grau === value} disabled={Boolean(busy)} onClick={() => setGrau(value)}>
                {value}º grau
              </button>
            ))}
          </div>
          <button
            type="button"
            className="iconButton"
            onClick={() => void reload()}
            aria-label="Recarregar status do contexto"
            title="Recarregar"
          >
            <RefreshCcw size={15} />
          </button>
        </div>
      </header>

      {error && (
        <p className="vaultError" role="alert">
          {error}
        </p>
      )}

      {capturadas.length > 0 && (
        <ul className="contextInstances">
          {capturadas.map((instancia) => (
            <li key={instancia.processo_instancia_id}>
              <strong>
                {instancia.sistema} · {instancia.tribunal} · {instancia.grau}º grau
              </strong>
              {instancia.captura ? (
                <>
                  <span
                    className="pill"
                    title={
                      instancia.captura.fonte === "upload"
                        ? "Arquivos e escopo declarados pelo advogado; não comprovam a íntegra do tribunal"
                        : instancia.captura.fonte === "mni"
                        ? "Lido pelo canal oficial do tribunal, sem usar o seu computador"
                        : "Lido pelo seu computador pareado, com o seu login"
                    }
                  >
                    {instancia.captura.fonte === "upload" ? "Envio pelo advogado" : instancia.captura.fonte === "mni" ? "Direto do tribunal" : "Seu computador"}
                  </span>
                  <span className="contextMeta">
                    {instancia.captura.status}
                    {" · "}
                    {instancia.captura.captured_count}/{instancia.captura.expected_count} documentos
                    {instancia.captura.error_code ? ` · motivo: ${instancia.captura.error_code}` : ""}
                    {instancia.captura.completed_at
                      ? ` · em ${new Date(instancia.captura.completed_at).toLocaleString("pt-BR")}`
                      : ""}
                  </span>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {uiState === "incomplete" && pendentes > 0 && (
        <p className="contextPending">{pendentes} documentos pendentes</p>
      )}

      <div className="contextDrop">
        <FileUp size={20} aria-hidden="true" />
        <div className="contextDropText">
          <strong>{onReceiveDocuments ? "Receba documentos do processo" : `Envie os autos do ${grau}º grau`}</strong>
          <span>{onReceiveDocuments ? "Acrescente arquivos ao conjunto existente e confira o destino do envio." : "PDF, um ou vários arquivos. Um novo envio substitui o inventário anterior deste grau."}</span>
        </div>
        <div className="contextActions">
          {onReceiveDocuments ? <button className="toolbarButton" disabled={receivingDisabled} onClick={onReceiveDocuments}><Upload size={14} />Receber documentos</button> : <label className="toolbarButton contextUpload">
            {busy === "upload" ? <Loader2 className="spin" size={14} /> : <Upload size={14} />}
            Escolher arquivos
            <input
              type="file"
              multiple
              accept="application/pdf"
              aria-label="Enviar os autos que você baixou no tribunal"
              disabled={busy === "upload"}
              onChange={(event) => void enviar(event.target.files)}
            />
          </label>}
          {!assistedOnly && blocked && !overrideOk && (
            <button className="toolbarButton" onClick={() => setShowOverride(true)}>
              <ShieldAlert size={14} /> Liberar excepcionalmente
            </button>
          )}
        </div>
      </div>

      {contexto && (
        <dl className="contextStats" aria-live="polite">
          <div><dt>Recebidos</dt><dd>{contexto.documents_total ?? 0}</dd></div>
          <div><dt>Extraídos</dt><dd>{contexto.documents_extracted ?? 0}</dd></div>
          <div><dt>Resumidos</dt><dd>{contexto.documents_summarized ?? 0}</dd></div>
        </dl>
      )}
      {blocked && (contexto?.documents_total ?? 0) > 0 && <LoadingButton className="toolbarButton compact contextRetry" loading={busy === "processar"} disabled={Boolean(busy)} onClick={() => void reprocessar()}>Retomar processamento</LoadingButton>}

      <details className="contextDeclaration">
        <summary>O processo não possui autos no {grau}º grau</summary>
        <div className="officeForm contextDeclarationBody">
          <p>Declare somente após conferir. A justificativa ficará registrada com seu usuário.</p>
          <label>Justificativa da ausência de autos<textarea rows={3} value={absence} disabled={Boolean(busy)} onChange={(e) => setAbsence(e.target.value)} /></label>
          <LoadingButton loading={busy === "ausencia"} disabled={Boolean(busy) || absence.trim().length < 20} onClick={() => void declararAusencia()}>Registrar declaração</LoadingButton>
        </div>
      </details>

      {blocked && !overrideOk && (
        <p className="contextBlockedReason">
          <Info size={14} aria-hidden="true" />
          <span>
            O contexto ainda possui pendências: confira os graus, os arquivos e o processamento.
            O envio manual registra o que foi enviado e não comprova a íntegra dos autos no tribunal.
          </span>
        </p>
      )}

      {!assistedOnly && showOverride && (
        <div className="contextOverride" role="dialog" aria-label="Liberação excepcional">
          <p className="contextOverrideWarning">
            ⚠ A peça gerada sem o contexto completo pode omitir fatos dos autos. A
            liberação vale para um único uso, expira em 30 minutos e fica
            registrada em auditoria com o seu nome.
          </p>
          <textarea
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
            placeholder="Justificativa (mínimo 20 caracteres)"
            rows={3}
          />
          <div>
            <button
              className="toolbarButton compact"
              disabled={justification.trim().length < 20 || busy === "override"}
              onClick={() => void liberar()}
            >
              Confirmar liberação
            </button>
            <button className="toolbarButton compact" onClick={() => setShowOverride(false)}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
