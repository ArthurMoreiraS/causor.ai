"use client";

import { ExternalLink, KeyRound, LockKeyhole, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import {
  CredencialAssinatura,
  desativarCredencial,
  listarCredenciais
} from "@/lib/api";
import { LoadingButton, Modal, Skeleton } from "./ui";
import { useToast } from "./Toast";

const PJE_HELP_URL = "https://www.cnj.jus.br/pje/";

function pjeSessionLabel(credencial: CredencialAssinatura): string {
  if (credencial.provedor !== "PJeSession") return credencial.provedor;
  return credencial.tribunal ? `PJe · ${credencial.tribunal}` : "PJe";
}

export default function VaultSection({ offline }: { offline: boolean }) {
  const toast = useToast();
  const [credenciais, setCredenciais] = useState<CredencialAssinatura[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConnect, setShowConnect] = useState(false);

  async function reload() {
    try {
      setCredenciais(await listarCredenciais());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar credenciais");
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
  }, [offline]);

  async function desativar(credencial: CredencialAssinatura) {
    setBusy(`off-${credencial.id}`);
    try {
      await desativarCredencial(credencial.id);
      await reload();
      toast({ kind: "success", title: "Sessão desativada" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível desativar");
    } finally {
      setBusy(null);
    }
  }

  const sessions = credenciais.filter((c) => c.provedor === "PJeSession" && c.ativo);
  const outras = credenciais.filter((c) => c.provedor !== "PJeSession");

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Conexão de tribunal (vault)</span>
      <small className="settingsHint vaultHint">
        <LockKeyhole size={13} />
        O Causor guarda apenas a sessão autenticada do tribunal (cookie), nunca o
        certificado, a senha ou o PIN. A assinatura continua no PJeOffice da sua máquina.
      </small>

      <LoadingButton
        className="toolbarButton primary compact vaultSubmit"
        disabled={offline}
        loading={busy === "connect"}
        icon={<KeyRound size={14} />}
        onClick={() => setShowConnect(true)}
      >
        Conectar PJe
      </LoadingButton>

      {error ? <small className="settingsHint vaultError">{error}</small> : null}

      <div className="vaultList">
        {loading ? (
          <>
            <Skeleton height={50} radius={8} />
            <Skeleton height={50} radius={8} />
          </>
        ) : sessions.length ? (
          sessions.map((credencial) => (
            <article className="vaultItem" key={credencial.id}>
              <div>
                <strong>{pjeSessionLabel(credencial)}</strong>
                <div className="pill ativa">Conectado</div>
              </div>
              <LoadingButton
                className="toolbarButton compact"
                disabled={offline}
                loading={busy === `off-${credencial.id}`}
                onClick={() => void desativar(credencial)}
              >
                Desativar
              </LoadingButton>
            </article>
          ))
        ) : (
          <small className="settingsHint">
            Nenhum tribunal conectado ainda. Use “Conectar PJe” acima.
          </small>
        )}
      </div>

      {outras.length > 0 ? (
        <small className="settingsHint vaultHint">
          <LockKeyhole size={13} />
          Referências de assinatura em nuvem (não habilitam protocolo direto hoje):
          {outras.map((c) => ` ${c.provedor}`).join(" ·")}
        </small>
      ) : null}

      {showConnect ? (
        <ConectarPjeModal offline={offline} onClose={() => setShowConnect(false)} />
      ) : null}
    </div>
  );
}

function ConectarPjeModal({ offline, onClose }: { offline: boolean; onClose: () => void }) {
  const [tribunal, setTribunal] = useState("TJSP");
  const [urlBase, setUrlBase] = useState("https://pje.tjsp.jus.br/pje");

  const comando = `python -m app.cli pje-capture-session \\
  --usuario <seu-id> \\
  --tribunal ${tribunal} \\
  --url-base ${urlBase}`;

  return (
    <Modal onClose={onClose} labelledBy="conectarPjeTitle">
      <h3 id="conectarPjeTitle">Conectar PJe</h3>
      <p className="protocolarResumo">
        A captura da sessão abre o PJe no seu computador para você logar uma vez com
        certificado digital. O Causor guarda só o cookie de sessão — o certificado e o PIN
        ficam no seu PJeOffice, nunca entram no sistema.
      </p>

      <div className="protocolarAviso">
        <Terminal size={16} />
        <span>
          No piloto, esta etapa roda no terminal da sua máquina (o backend não consegue
          abrir janela na sua tela). Copie o comando abaixo e execute localmente.
        </span>
      </div>

      <label className="protocolarCredencial">
        Tribunal
        <input value={tribunal} onChange={(e) => setTribunal(e.target.value)} />
      </label>

      <label className="protocolarCredencial">
        URL base do PJe
        <input value={urlBase} onChange={(e) => setUrlBase(e.target.value)} />
      </label>

      <pre className="vaultComando">{comando}</pre>

      <div className="protocolarHint">
        <ExternalLink size={13} /> Após logar no PJe e o painel carregar, volte ao terminal
        e pressione <strong>Enter</strong>. A sessão aparece aqui como “PJe · {tribunal}”.
      </div>

      <div className="modalActions">
        <button className="toolbarButton" onClick={onClose} disabled={offline}>
          Fechar
        </button>
        <a
          className="toolbarButton"
          href={PJE_HELP_URL}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink size={14} /> Ajuda do PJe
        </a>
      </div>
    </Modal>
  );
}
