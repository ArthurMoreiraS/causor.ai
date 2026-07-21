"use client";

import { FileSearch, ShieldCheck, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  cadastrarMniCredencial,
  listarMniCredenciais,
  MniCredencial,
  revogarMniCredencial,
  testarMniCredencial
} from "@/lib/api";
import { AsyncState, LoadingButton, Skeleton } from "./ui";

// Consulta oficial (MNI): com credencial ativa, a captura dos autos usa o
// webservice do tribunal no backend em vez do agente local. A senha vai
// direto para o vault e nunca volta na API (lista mascarada).
export default function MniSection({ offline }: { offline: boolean }) {
  const [credenciais, setCredenciais] = useState<MniCredencial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [tribunal, setTribunal] = useState("");
  const [idConsultante, setIdConsultante] = useState("");
  const [senha, setSenha] = useState("");
  const [numeroTeste, setNumeroTeste] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setCredenciais(await listarMniCredenciais());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar credenciais MNI");
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
  }, [offline, reload]);

  async function cadastrar() {
    setBusy("create");
    setFeedback(null);
    try {
      await cadastrarMniCredencial({
        tribunal: tribunal.trim().toUpperCase(),
        id_consultante: idConsultante.trim(),
        senha
      });
      setTribunal("");
      setIdConsultante("");
      setSenha("");
      await reload();
      setFeedback("Credencial MNI cadastrada.");
    } catch (err) {
      setFeedback(
        err instanceof Error ? err.message : "Falha ao cadastrar credencial MNI"
      );
    } finally {
      setBusy(null);
    }
  }

  async function revogar(credencialId: number) {
    setBusy(`revoke-${credencialId}`);
    try {
      await revogarMniCredencial(credencialId);
      await reload();
    } finally {
      setBusy(null);
    }
  }

  async function testar(credencialId: number) {
    if (!numeroTeste.trim()) {
      setFeedback("Informe um numero de processo para o teste.");
      return;
    }
    setBusy(`test-${credencialId}`);
    setFeedback(null);
    try {
      const result = await testarMniCredencial(credencialId, numeroTeste.trim());
      setFeedback(
        result.ok
          ? `Conexao MNI ok (${result.documentos ?? 0} documento(s) listados).`
          : `Teste falhou: ${result.error_code}`
      );
      await reload();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Falha ao testar credencial MNI");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Consulta oficial (MNI)</span>
      <small className="settingsHint vaultHint">
        <FileSearch size={13} />
        Credencial de consulta obtida no credenciamento junto ao tribunal. Com ela
        ativa, a captura dos autos usa o webservice oficial no servidor — sem depender
        do computador do advogado estar ligado. A senha vai direto para o vault.
      </small>

      <div className="vaultList">
        <AsyncState
          loading={loading}
          error={error}
          empty={!credenciais.length}
          skeleton={<Skeleton height={50} radius={8} />}
          emptyState={
            <small className="settingsHint">
              Nenhuma credencial MNI cadastrada ainda.
            </small>
          }
          retrying={retrying}
          onRetry={() => {
            setRetrying(true);
            void reload().finally(() => setRetrying(false));
          }}
        >
          {credenciais.map((cred) => (
            <article className="vaultItem" key={cred.id}>
              <div>
                <strong>{cred.tribunal}</strong>
                <div className={cred.ativo ? "pill online" : "pill revogado"}>
                  {cred.ativo ? "Ativa" : "Revogada"}
                </div>
                <span>{cred.id_consultante_mask}</span>
                <span>
                  {cred.last_validated_at
                    ? `validada ${new Date(cred.last_validated_at).toLocaleString("pt-BR")}`
                    : "nunca validada"}
                </span>
              </div>
              {cred.ativo ? (
                <div className="modalActions">
                  <LoadingButton
                    className="toolbarButton compact"
                    loading={busy === `test-${cred.id}`}
                    icon={<ShieldCheck size={14} />}
                    onClick={() => void testar(cred.id)}
                  >
                    Testar
                  </LoadingButton>
                  <LoadingButton
                    className="toolbarButton compact danger"
                    loading={busy === `revoke-${cred.id}`}
                    icon={<Unplug size={14} />}
                    onClick={() => void revogar(cred.id)}
                  >
                    Revogar
                  </LoadingButton>
                </div>
              ) : null}
            </article>
          ))}
        </AsyncState>
      </div>

      <label className="settingsField">
        Processo para teste
        <input
          value={numeroTeste}
          disabled={offline}
          onChange={(event) => setNumeroTeste(event.target.value)}
          placeholder="numero CNJ para validar a conexao"
        />
      </label>

      <label className="settingsField">
        Tribunal
        <input
          value={tribunal}
          disabled={offline}
          onChange={(event) => setTribunal(event.target.value)}
          placeholder="TJMG"
        />
      </label>
      <label className="settingsField">
        Id consultante
        <input
          value={idConsultante}
          disabled={offline}
          onChange={(event) => setIdConsultante(event.target.value)}
          placeholder="CPF/CNPJ do credenciamento"
        />
      </label>
      <label className="settingsField">
        Senha
        <input
          type="password"
          value={senha}
          disabled={offline}
          onChange={(event) => setSenha(event.target.value)}
        />
      </label>
      <LoadingButton
        className="toolbarButton primary compact vaultSubmit"
        disabled={offline || !tribunal.trim() || !idConsultante.trim() || !senha}
        loading={busy === "create"}
        icon={<FileSearch size={14} />}
        onClick={() => void cadastrar()}
      >
        Cadastrar
      </LoadingButton>

      {feedback ? (
        <small className="settingsHint" role="status">
          {feedback}
        </small>
      ) : null}
    </div>
  );
}
