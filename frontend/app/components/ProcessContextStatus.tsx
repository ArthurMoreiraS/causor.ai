"use client";

import { FileSearch, Loader2, RefreshCcw, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import {
  AutosStatus,
  capturarAutos,
  criarOverrideContexto,
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
  if (!status || status.instancias.length === 0) return "not_captured";
  const capturas = status.instancias.map((i) => i.captura);
  if (capturas.every((c) => c === null)) return "not_captured";
  if (capturas.some((c) => c && ["queued", "enumerating", "downloading", "verifying"].includes(c.status))) {
    return "capturing";
  }
  if (capturas.some((c) => c && ["incomplete", "failed"].includes(c.status))) return "incomplete";
  if (capturas.every((c) => c === null || c.status === "complete" || c.status === "not_applicable")) {
    return "ready";
  }
  return "blocked";
}

const STATE_LABEL: Record<ContextUiState, string> = {
  not_captured: "Autos não capturados",
  capturing: "Capturando autos…",
  incomplete: "Contexto incompleto",
  processing: "Processando documentos…",
  ready: "Contexto completo",
  stale: "Contexto desatualizado",
  blocked: "Bloqueado"
};

export default function ProcessContextStatus({ processoId }: { processoId: number }) {
  const [status, setStatus] = useState<AutosStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [justification, setJustification] = useState("");
  const [overrideOk, setOverrideOk] = useState(false);
  const [showWizard, setShowWizard] = useState(false);

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
                      instancia.captura.fonte === "mni"
                        ? "Capturado pelo webservice oficial do tribunal (MNI), direto no servidor"
                        : "Capturado pelo computador pareado do advogado"
                    }
                  >
                    {instancia.captura.fonte === "mni" ? "Oficial (MNI)" : "Agente local"}
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
        <button
          className="toolbarButton compact"
          disabled={busy === "capturar" || uiState === "capturing"}
          onClick={() => void capturar()}
        >
          {uiState === "not_captured" ? "Capturar autos" : "Retentar pendências"}
        </button>
        <button
          className="toolbarButton primary compact"
          onClick={() => {
            if (blocked && !overrideOk) setShowWizard(true);
          }}
        >
          Gerar minuta
        </button>
        {blocked && !overrideOk && (
          <button className="toolbarButton compact" onClick={() => setShowOverride(true)}>
            <ShieldAlert size={13} /> Liberar excepcionalmente
          </button>
        )}
      </div>

      {blocked && !overrideOk && (
        <p className="contextBlockedReason">
          Minuta e protocolo ficam bloqueados até a captura integral dos autos ser
          comprovada (enumeração conferida, arquivos verificados por hash, texto
          extraído e resumos citados).
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
