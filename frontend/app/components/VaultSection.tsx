"use client";

import { LockKeyhole, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  cadastrarCredencial,
  CredencialAssinatura,
  desativarCredencial,
  listarCredenciais
} from "@/lib/api";
import SearchSelect from "./SearchSelect";
import { LoadingButton, Skeleton } from "./ui";
import { useToast } from "./Toast";

const PROVEDORES = ["BirdID", "VIDaaS", "SafeID", "Certisign Cloud"];

export default function VaultSection({ offline }: { offline: boolean }) {
  const toast = useToast();
  const [credenciais, setCredenciais] = useState<CredencialAssinatura[]>([]);
  const [provedor, setProvedor] = useState(PROVEDORES[0]);
  const [referencia, setReferencia] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const providerOptions = useMemo(
    () => PROVEDORES.map((provider) => ({ value: provider, label: provider })),
    []
  );

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
      toast({ kind: "success", title: "Credencial cadastrada", description: `${provedor} adicionado ao vault.` });
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
      toast({ kind: "success", title: "Credencial desativada" });
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

      <form
        className="vaultForm"
        onSubmit={(event) => {
          event.preventDefault();
          void cadastrar();
        }}
      >
        <div className="settingsRow vaultFields">
          <label>
            Provedor
            <SearchSelect
              value={provedor}
              name="provedor"
              options={providerOptions}
              disabled={offline || busy === "create"}
              onChange={setProvedor}
            />
          </label>
          <label>
            Referência externa
            <input
              value={referencia}
              disabled={offline || busy === "create"}
              placeholder="ID do certificado no provedor"
              onChange={(e) => setReferencia(e.target.value)}
            />
          </label>
        </div>
        <LoadingButton
          type="submit"
          className="toolbarButton primary compact vaultSubmit"
          disabled={offline}
          loading={busy === "create"}
          icon={<ShieldCheck size={14} />}
        >
          Cadastrar credencial
        </LoadingButton>
      </form>

      {error ? <small className="settingsHint vaultError">{error}</small> : null}

      <div className="vaultList">
        {loading ? (
          <>
            <Skeleton height={50} radius={8} />
            <Skeleton height={50} radius={8} />
          </>
        ) : credenciais.length ? (
          credenciais.map((credencial) => (
            <article className="vaultItem" key={credencial.id}>
              <div>
                <strong>{credencial.provedor}</strong>
                <span className="mono">{credencial.referencia_vault}</span>
              </div>
              {credencial.ativo ? (
                <LoadingButton
                  className="toolbarButton compact"
                  disabled={offline}
                  loading={busy === `off-${credencial.id}`}
                  onClick={() => void desativar(credencial)}
                >
                  Desativar
                </LoadingButton>
              ) : (
                <span className="pill inativa">Inativa</span>
              )}
            </article>
          ))
        ) : (
          <small className="settingsHint">Nenhuma credencial cadastrada ainda.</small>
        )}
      </div>
    </div>
  );
}
