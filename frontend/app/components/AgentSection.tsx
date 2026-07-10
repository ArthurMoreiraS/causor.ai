"use client";

import { Laptop, RefreshCcw, Unplug } from "lucide-react";
import { useEffect, useState } from "react";
import {
  AgentInstallation,
  AgentPairingCode,
  criarCodigoPareamento,
  listarAgentes,
  revogarAgente
} from "@/lib/api";
import { LoadingButton, SkeletonText } from "./ui";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
const ONLINE_WINDOW_MS = 90_000;

export function isOnline(lastSeenAt: string | null, now: Date = new Date()): boolean {
  if (!lastSeenAt) return false;
  const seen = new Date(lastSeenAt).getTime();
  return Number.isFinite(seen) && now.getTime() - seen <= ONLINE_WINDOW_MS;
}

export function pairingCommand(code: string): string {
  return `python -m app.local_agent pair --api ${API_BASE} --code ${code} --name "Meu computador"`;
}

export default function AgentSection({ offline }: { offline: boolean }) {
  const [agentes, setAgentes] = useState<AgentInstallation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pairing, setPairing] = useState<AgentPairingCode | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<number | null>(null);

  async function reload() {
    try {
      setAgentes(await listarAgentes());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar agentes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (offline) {
      setLoading(false);
      return;
    }
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offline]);

  async function gerarCodigo() {
    setBusy("pair");
    try {
      setPairing(await criarCodigoPareamento());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar código de pareamento");
    } finally {
      setBusy(null);
    }
  }

  async function revogar(id: number) {
    setBusy(`revoke-${id}`);
    try {
      await revogarAgente(id);
      setConfirmRevoke(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao revogar agente");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="vaultSection">
      <header className="vaultHead">
        <div>
          <strong>
            <Laptop size={15} style={{ verticalAlign: "-2px", marginRight: 6 }} />
            Agente local
          </strong>
          <span className="vaultHint">
            O agente roda no computador do advogado e executa leitura/protocolo com a sessão do
            tribunal local. Nenhum token, cookie ou certificado sai daquela máquina.
          </span>
        </div>
        <button
          className="toolbarButton compact"
          disabled={offline || loading}
          onClick={() => void reload()}
          aria-label="Recarregar agentes"
        >
          <RefreshCcw size={14} />
        </button>
      </header>

      {loading ? (
        <SkeletonText lines={2} />
      ) : error ? (
        <p className="vaultError" role="alert">
          {error}
        </p>
      ) : agentes.length === 0 ? (
        <p className="vaultEmpty">Nenhum computador pareado ainda.</p>
      ) : (
        <ul className="vaultList">
          {agentes.map((agente) => {
            const online = isOnline(agente.last_seen_at);
            return (
              <li key={agente.id} className="vaultItem">
                <div>
                  <strong>{agente.nome}</strong>{" "}
                  <span className={online ? "badgeOk" : "badgeMuted"}>
                    {online ? "Online" : "Offline"}
                  </span>
                  <div className="vaultMeta">
                    {agente.version ? `v${agente.version}` : "versão desconhecida"}
                    {agente.last_seen_at
                      ? ` · visto ${new Date(agente.last_seen_at).toLocaleString("pt-BR")}`
                      : ""}
                    {agente.ativo ? "" : " · revogado"}
                  </div>
                </div>
                {agente.ativo &&
                  (confirmRevoke === agente.id ? (
                    <span>
                      <LoadingButton
                        loading={busy === `revoke-${agente.id}`}
                        className="toolbarButton compact"
                        onClick={() => void revogar(agente.id)}
                      >
                        Confirmar revogação
                      </LoadingButton>
                      <button
                        className="toolbarButton compact"
                        onClick={() => setConfirmRevoke(null)}
                      >
                        Cancelar
                      </button>
                    </span>
                  ) : (
                    <button
                      className="toolbarButton compact"
                      onClick={() => setConfirmRevoke(agente.id)}
                    >
                      <Unplug size={14} /> Revogar
                    </button>
                  ))}
              </li>
            );
          })}
        </ul>
      )}

      <div className="vaultActions">
        <LoadingButton
          loading={busy === "pair"}
          disabled={offline}
          onClick={() => void gerarCodigo()}
        >
          Parear este computador
        </LoadingButton>
      </div>

      {pairing && (
        <div className="vaultPairing">
          <p>
            Rode este comando no computador do advogado (código expira em{" "}
            {new Date(pairing.expires_at).toLocaleTimeString("pt-BR")}):
          </p>
          <pre className="vaultCommand">
            <code>{pairingCommand(pairing.code)}</code>
          </pre>
        </div>
      )}
    </section>
  );
}
