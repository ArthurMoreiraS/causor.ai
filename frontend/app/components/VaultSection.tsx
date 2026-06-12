"use client";

import { Loader2, LockKeyhole, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import {
  cadastrarCredencial,
  CredencialAssinatura,
  desativarCredencial,
  listarCredenciais
} from "@/lib/api";

const PROVEDORES = ["BirdID", "VIDaaS", "SafeID", "Certisign Cloud"];

export default function VaultSection({ offline }: { offline: boolean }) {
  const [credenciais, setCredenciais] = useState<CredencialAssinatura[]>([]);
  const [provedor, setProvedor] = useState(PROVEDORES[0]);
  const [referencia, setReferencia] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      setCredenciais(await listarCredenciais());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar credenciais");
    }
  }

  useEffect(() => {
    if (!offline) void reload();
  }, [offline]);

  async function cadastrar() {
    if (referencia.trim().length < 4) {
      setError("Informe a referência externa do certificado (mínimo 4 caracteres).");
      return;
    }
    setBusy("create");
    setError(null);
    try {
      await cadastrarCredencial(provedor, referencia.trim());
      setReferencia("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível cadastrar a credencial");
    } finally {
      setBusy(null);
    }
  }

  async function desativar(credencial: CredencialAssinatura) {
    setBusy(`off-${credencial.id}`);
    try {
      await desativarCredencial(credencial.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível desativar a credencial");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Certificado de assinatura (vault)</span>
      <small className="settingsHint vaultHint">
        <LockKeyhole size={13} />
        O Causor guarda apenas uma referência segura ao certificado no provedor em nuvem. Senha,
        certificado e chave privada nunca entram no sistema, em prompts ou em logs.
      </small>

      <div className="settingsRow">
        <label>
          Provedor
          <select value={provedor} onChange={(e) => setProvedor(e.target.value)}>
            {PROVEDORES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Referência externa
          <input
            value={referencia}
            placeholder="ID do certificado no provedor"
            onChange={(e) => setReferencia(e.target.value)}
          />
        </label>
      </div>
      <button
        className="toolbarButton compact"
        disabled={offline || busy === "create"}
        onClick={() => void cadastrar()}
      >
        {busy === "create" ? <Loader2 className="spin" size={14} /> : <ShieldCheck size={14} />}
        Cadastrar credencial
      </button>

      {error ? <small className="settingsHint vaultError">{error}</small> : null}

      <div className="vaultList">
        {credenciais.map((credencial) => (
          <article className="vaultItem" key={credencial.id}>
            <div>
              <strong>{credencial.provedor}</strong>
              <span className="mono">{credencial.referencia_vault}</span>
            </div>
            {credencial.ativo ? (
              <button
                className="toolbarButton compact"
                disabled={offline || busy === `off-${credencial.id}`}
                onClick={() => void desativar(credencial)}
              >
                {busy === `off-${credencial.id}` ? <Loader2 className="spin" size={14} /> : null}
                Desativar
              </button>
            ) : (
              <span className="pill rascunho">Inativa</span>
            )}
          </article>
        ))}
        {!credenciais.length ? (
          <small className="settingsHint">Nenhuma credencial cadastrada ainda.</small>
        ) : null}
      </div>
    </div>
  );
}
