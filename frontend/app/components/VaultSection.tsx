"use client";

import { ExternalLink, KeyRound, LockKeyhole, MonitorSmartphone } from "lucide-react";
import { useEffect, useState } from "react";
import {
  capturarSessaoTribunal,
  CourtRouting,
  CredencialAssinatura,
  desativarCredencial,
  listarCredenciais,
  resolverRota
} from "@/lib/api";
import { LoadingButton, Modal, Skeleton } from "./ui";
import { useToast } from "./Toast";

const PJE_HELP_URL = "https://www.cnj.jus.br/pje/";

// Tribunais oferecidos no seletor (verificados no registro aparecem primeiro).
const TRIBUNAIS = ["TJSP", "TJMG", "TRT2", "TJRS", "TRF4", "TJBA", "TJDFT", "TRF3", "TJPR"];

function courtSessionLabel(credencial: CredencialAssinatura): string {
  const sistema = credencial.sistema ?? "Tribunal";
  return credencial.tribunal ? `${sistema} · ${credencial.tribunal}` : sistema;
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

  const sessions = credenciais.filter((c) => c.tipo === "session" && c.ativo);
  const outras = credenciais.filter((c) => c.tipo !== "session");

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
        Conectar tribunal
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
                <strong>{courtSessionLabel(credencial)}</strong>
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
            Nenhum tribunal conectado ainda. Use “Conectar tribunal” acima.
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
        <ConectarTribunalModal
          offline={offline}
          onClose={() => setShowConnect(false)}
          onConnected={async () => {
            await reload();
            setShowConnect(false);
          }}
        />
      ) : null}
    </div>
  );
}

function ConectarTribunalModal({
  offline,
  onClose,
  onConnected
}: {
  offline: boolean;
  onClose: () => void;
  onConnected: () => void | Promise<void>;
}) {
  const toast = useToast();
  const [tribunal, setTribunal] = useState("TJSP");
  const [grau, setGrau] = useState("1");
  const [rota, setRota] = useState<CourtRouting | null>(null);
  const [resolvendo, setResolvendo] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let ok = true;
    setResolvendo(true);
    setRota(null);
    resolverRota(tribunal, grau)
      .then((r) => {
        if (ok) setRota(r);
      })
      .catch(() => {
        if (ok) setRota(null);
      })
      .finally(() => {
        if (ok) setResolvendo(false);
      });
    return () => {
      ok = false;
    };
  }, [tribunal, grau]);

  const semUrl = !resolvendo && (!rota || !rota.url_login);

  async function conectar() {
    setBusy(true);
    try {
      await capturarSessaoTribunal(tribunal, grau);
      toast({ kind: "success", title: "Tribunal conectado" });
      await onConnected();
    } catch (e) {
      toast({
        kind: "error",
        title: e instanceof Error ? e.message : "Falha ao conectar o tribunal"
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose} labelledBy="conectarTribunalTitle">
      <h3 id="conectarTribunalTitle">Conectar tribunal</h3>
      <p className="protocolarResumo">
        Abre o portal do tribunal no seu computador para você logar uma vez com
        certificado digital. O Causor guarda só o cookie de sessão — o certificado e o PIN
        ficam no seu PJeOffice/Web Signer, nunca entram no sistema.
      </p>

      <div className="protocolarAviso">
        <MonitorSmartphone size={16} />
        <span>
          Ao clicar em <strong>Conectar</strong>, uma janela do navegador abre na sua tela
          apontando para o portal certo. Faça o login e o painel do advogado carregar; a
          sessão aparece aqui como conectada.
        </span>
      </div>

      <label className="protocolarCredencial">
        Tribunal
        <select value={tribunal} onChange={(e) => setTribunal(e.target.value)}>
          {TRIBUNAIS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="protocolarCredencial">
        Grau
        <select value={grau} onChange={(e) => setGrau(e.target.value)}>
          <option value="1">1º grau</option>
          <option value="2">2º grau</option>
        </select>
      </label>

      <div className="protocolarHint">
        {resolvendo ? (
          "Resolvendo o sistema do tribunal…"
        ) : rota ? (
          <>
            Destino: <strong>{rota.sistema}</strong>
            {rota.url_login ? (
              <>
                {" · "}
                <span className="mono">{rota.url_login}</span>
              </>
            ) : (
              " · URL não cadastrada no registro (não é possível conectar automaticamente ainda)"
            )}
          </>
        ) : (
          "Tribunal sem rota no registro."
        )}
      </div>

      <div className="modalActions">
        <button className="toolbarButton" onClick={onClose} disabled={busy}>
          Fechar
        </button>
        <a className="toolbarButton" href={PJE_HELP_URL} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Ajuda
        </a>
        <LoadingButton
          className="toolbarButton primary"
          loading={busy}
          disabled={offline || busy || semUrl}
          icon={<KeyRound size={14} />}
          onClick={() => void conectar()}
        >
          Conectar
        </LoadingButton>
      </div>
    </Modal>
  );
}
