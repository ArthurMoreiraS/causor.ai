"use client";

import { FileSearch, Loader2, RefreshCcw, ShieldAlert, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import {
  AutosStatus,
  capturarAutos,
  criarOverrideContexto,
  declararGrauNaoAplicavel,
  reprocessarAutos,
  enviarAutos,
  statusAutos
} from "@/lib/api";
import { humanError } from "@/lib/errors";
import AcessoTribunalWizard from "./AcessoTribunalWizard";

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

const STATE_LABEL: Record<ContextUiState, string> = {
  not_captured: "Autos não capturados",
  capturing: "Capturando autos…",
  incomplete: "Contexto incompleto",
  processing: "Processando documentos…",
  ready: "Contexto disponível para revisão",
  stale: "Contexto desatualizado",
  blocked: "Bloqueado"
};

export default function ProcessContextStatus({ processoId, onReceiveDocuments, receivingDisabled = false }: {
  processoId: number; onReceiveDocuments?: () => void; receivingDisabled?: boolean;
}) {
  const [status, setStatus] = useState<AutosStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [justification, setJustification] = useState("");
  const [overrideOk, setOverrideOk] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [grau, setGrau] = useState("1");
  const [absence, setAbsence] = useState("");

  async function reload() {
    try {
      setStatus(await statusAutos(processoId));
      setError(null);
    } catch (err) {
      setError(humanError(err, "Falha ao carregar status dos autos"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), 5000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processoId]);

  async function capturar() {
    setBusy("capturar");
    try {
      await capturarAutos(processoId);
      await reload();
    } catch (err) {
      setError(humanError(err, "Falha ao iniciar captura"));
    } finally {
      setBusy(null);
    }
  }

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
      <section className="contextStatus">
        <Loader2 className="spin" size={14} /> Carregando contexto do processo…
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

  return (
    <section className="contextStatus">
      <header>
        <strong>
          <FileSearch size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />
          {STATE_LABEL[uiState]}
        </strong>
        <button
          className="toolbarButton compact"
          onClick={() => void reload()}
          aria-label="Recarregar status do contexto"
        >
          <RefreshCcw size={13} />
        </button>
      </header>

      {error && (
        <p className="vaultError" role="alert">
          {error}
        </p>
      )}

      {status && (
        <ul className="contextInstances">
          {status.instancias.map((instancia) => (
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
              ) : (
                <span className="contextMeta">sem captura</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {uiState === "incomplete" && pendentes > 0 && (
        <p className="contextPending">{pendentes} documentos pendentes</p>
      )}

      <div className="contextActions">
        <label>Grau dos autos
          <select aria-label="Grau dos autos" value={grau} onChange={(e) => setGrau(e.target.value)}>
            <option value="1">1º grau</option><option value="2">2º grau</option>
          </select>
        </label>
        <button
          className="toolbarButton compact"
          disabled={busy === "capturar" || uiState === "capturing"}
          onClick={() => void capturar()}
        >
          {uiState === "not_captured" ? "Capturar autos" : "Retentar pendências"}
        </button>
        {onReceiveDocuments ? <button className="toolbarButton compact" disabled={receivingDisabled} onClick={onReceiveDocuments}>Receber documentos</button> : <label className="toolbarButton compact contextUpload">
          {busy === "upload" ? <Loader2 className="spin" size={13} /> : <Upload size={13} />}
          Enviar os autos
          <input
            type="file"
            multiple
            accept="application/pdf"
            aria-label="Enviar os autos que você baixou no tribunal"
            disabled={busy === "upload"}
            onChange={(event) => void enviar(event.target.files)}
          />
        </label>}
        <button
          className="toolbarButton primary compact"
          onClick={() => {
            setShowWizard(true);
          }}
        >
          Ver acesso ao tribunal
        </button>
        {blocked && !overrideOk && (
          <button className="toolbarButton compact" onClick={() => setShowOverride(true)}>
            <ShieldAlert size={13} /> Liberar excepcionalmente
          </button>
        )}
      </div>

      <p>{onReceiveDocuments ? "Use Receber documentos para acrescentar arquivos ao conjunto existente e conferir o destino do envio." : "Envie o conjunto de arquivos do grau selecionado. Um novo envio substitui o inventário anterior desse grau."}</p>
      {status?.contexto && (
        <p aria-live="polite">
          {status.contexto.documents_extracted ?? 0} documentos extraídos · {status.contexto.documents_summarized ?? 0} resumidos de {status.contexto.documents_total ?? 0} recebidos.
        </p>
      )}
      {blocked && <button className="toolbarButton compact" disabled={!!busy} onClick={() => void reprocessar()}>Retomar processamento com falha</button>}
      <details>
        <summary>O processo não possui autos no {grau}º grau</summary>
        <p>Declare somente após conferir. A justificativa ficará registrada com seu usuário.</p>
        <textarea aria-label="Justificativa da ausência de autos" value={absence} onChange={(e) => setAbsence(e.target.value)} />
        <button disabled={!!busy || absence.trim().length < 20} onClick={() => void declararAusencia()}>Registrar declaração</button>
      </details>

      {blocked && !overrideOk && (
        <p className="contextBlockedReason">
          O contexto ainda possui pendências. Confira os graus, os arquivos e o processamento.
          O envio manual declara o escopo recebido; não comprova a íntegra dos autos no tribunal.
        </p>
      )}

      {showWizard && (
        <AcessoTribunalWizard
          processoId={processoId}
          onReady={() => {
            setShowWizard(false);
            void reload();
          }}
          onClose={() => setShowWizard(false)}
        />
      )}

      {showOverride && (
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
