"use client";

import { AlertTriangle, Copy, Laptop, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  AgentInstallation,
  AgentPairingCode,
  criarCodigoPareamento,
  listarAgentes,
  revogarAgente
} from "@/lib/api";
import { humanError } from "@/lib/errors";
import { AsyncState, LoadingButton, Modal, Skeleton } from "./ui";
import { useToast } from "./Toast";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
const ONLINE_WINDOW_MS = 90_000;
// A saúde online/offline depende do relógio (janela de 90s) e o pareamento
// termina fora da UI, no terminal: recarregar em intervalo mantém os dois
// visíveis sem exigir botão de atualizar.
const REFRESH_INTERVAL_MS = 30_000;

export function isOnline(lastSeenAt: string | null, now: Date = new Date()): boolean {
  if (!lastSeenAt) return false;
  const seen = new Date(lastSeenAt).getTime();
  return Number.isFinite(seen) && now.getTime() - seen <= ONLINE_WINDOW_MS;
}

export function pairingCommand(code: string): string {
  return `python -m app.local_agent pair --api ${API_BASE} --code ${code} --name "Meu computador"`;
}

function agentStatus(agente: AgentInstallation): { pill: string; label: string } {
  if (!agente.ativo) return { pill: "pill revogado", label: "Revogado" };
  return isOnline(agente.last_seen_at)
    ? { pill: "pill online", label: "Online" }
    : { pill: "pill offline", label: "Offline" };
}

function agentMeta(agente: AgentInstallation): string {
  const version = agente.version ? `v${agente.version}` : "versão desconhecida";
  const seen = agente.last_seen_at
    ? `visto ${new Date(agente.last_seen_at).toLocaleString("pt-BR")}`
    : "nunca conectou";
  return `${version} · ${seen}`;
}

export default function AgentSection({ offline }: { offline: boolean }) {
  const toast = useToast();
  const [agentes, setAgentes] = useState<AgentInstallation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pairing, setPairing] = useState<AgentPairingCode | null>(null);
  const [agenteToRevoke, setAgenteToRevoke] = useState<AgentInstallation | null>(null);

  const reload = useCallback(async () => {
    try {
      setAgentes(await listarAgentes());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Falha ao carregar os computadores pareados"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (offline) {
      setLoading(false);
      return;
    }
    void reload();
    const timer = window.setInterval(() => void reload(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [offline, reload]);

  async function gerarCodigo() {
    setBusy("pair");
    try {
      setPairing(await criarCodigoPareamento());
      setActionError(null);
    } catch (err) {
      setActionError(humanError(err, "Falha ao gerar o código de pareamento"));
    } finally {
      setBusy(null);
    }
  }

  async function copiarComando(code: string) {
    try {
      await navigator.clipboard.writeText(pairingCommand(code));
      toast({ kind: "success", title: "Comando copiado" });
    } catch {
      toast({
        kind: "error",
        title: "Não foi possível copiar",
        description: "Selecione o comando e copie manualmente."
      });
    }
  }

  async function revogar(agente: AgentInstallation) {
    setBusy(`revoke-${agente.id}`);
    try {
      await revogarAgente(agente.id);
      setAgenteToRevoke(null);
      setActionError(null);
      await reload();
      toast({
        kind: "success",
        title: `Acesso de ${agente.nome} revogado`,
        description: "O computador não executa mais leituras nem protocolos."
      });
    } catch (err) {
      setActionError(humanError(err, "Falha ao revogar o acesso do computador"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Seu computador</span>
      <small className="settingsHint vaultHint">
        <Laptop size={13} />
        Pareado uma vez, é ele que lê os autos e protocola, em todo tribunal. O
        login no portal é aberto pelo assistente quando necessário; nenhum token,
        cookie ou certificado sai daquela máquina.
      </small>

      <LoadingButton
        className="toolbarButton primary compact vaultSubmit"
        disabled={offline}
        loading={busy === "pair"}
        icon={<Laptop size={14} />}
        onClick={() => void gerarCodigo()}
      >
        {pairing ? "Gerar novo código" : "Parear este computador"}
      </LoadingButton>

      {pairing ? (
        <>
          <small className="settingsHint">
            Rode o comando no computador a parear — o código expira às{" "}
            {new Date(pairing.expires_at).toLocaleTimeString("pt-BR")}.
          </small>
          <pre className="vaultComando">
            <code>{pairingCommand(pairing.code)}</code>
          </pre>
          <button
            type="button"
            className="toolbarButton compact"
            onClick={() => void copiarComando(pairing.code)}
          >
            <Copy size={14} />
            Copiar comando
          </button>
        </>
      ) : null}

      <div className="vaultList">
        <AsyncState
          loading={loading}
          error={error}
          empty={!agentes.length}
          skeleton={
            <>
              <Skeleton height={50} radius={8} />
              <Skeleton height={50} radius={8} />
            </>
          }
          emptyState={
            <small className="settingsHint">
              Nenhum computador pareado ainda. Use “Parear este computador” acima.
            </small>
          }
          retrying={retrying}
          onRetry={() => {
            setRetrying(true);
            void reload().finally(() => setRetrying(false));
          }}
        >
          {agentes.map((agente) => {
            const status = agentStatus(agente);
            return (
              <article className="vaultItem" key={agente.id}>
                <div>
                  <strong>{agente.nome}</strong>
                  <div className={status.pill}>{status.label}</div>
                  <span>{agentMeta(agente)}</span>
                </div>
                {agente.ativo ? (
                  <button
                    type="button"
                    className="toolbarButton compact danger"
                    disabled={offline}
                    onClick={() => {
                      setActionError(null);
                      setAgenteToRevoke(agente);
                    }}
                  >
                    <Unplug size={14} />
                    Revogar
                  </button>
                ) : null}
              </article>
            );
          })}
        </AsyncState>
      </div>

      {actionError && !agenteToRevoke ? (
        <small className="settingsHint vaultError" role="alert">
          {actionError}
        </small>
      ) : null}

      {agenteToRevoke ? (
        <Modal
          onClose={() => {
            if (busy === null) setAgenteToRevoke(null);
          }}
          labelledBy="revokeAgentConfirmTitle"
          className="confirmCard"
        >
          <div className="confirmIcon danger" aria-hidden="true">
            <AlertTriangle size={18} />
          </div>
          <div className="confirmBody">
            <span className="settingsLabel" id="revokeAgentConfirmTitle">
              Revogar acesso de {agenteToRevoke.nome}?
            </span>
            <p>
              O computador perde o acesso imediatamente e deixa de executar leituras e
              protocolos. Para voltar a usá-lo, será preciso parear de novo.
            </p>
            {actionError ? (
              <small className="settingsHint vaultError" role="alert">
                {actionError}
              </small>
            ) : null}
          </div>
          <div className="modalActions">
            <button
              type="button"
              className="toolbarButton compact"
              disabled={busy !== null}
              onClick={() => setAgenteToRevoke(null)}
            >
              Cancelar
            </button>
            <LoadingButton
              className="toolbarButton compact danger confirmDanger"
              loading={busy === `revoke-${agenteToRevoke.id}`}
              icon={<Unplug size={14} />}
              onClick={() => void revogar(agenteToRevoke)}
            >
              Revogar acesso
            </LoadingButton>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
