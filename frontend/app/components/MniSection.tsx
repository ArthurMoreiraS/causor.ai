"use client";

import { ChevronDown, FileSearch, ShieldCheck, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  cadastrarMniCredencial,
  listarMniCredenciais,
  MniCredencial,
  revogarMniCredencial,
  testarMniCredencial
} from "@/lib/api";
import { humanError, mniErrorMessage } from "@/lib/errors";
import { AsyncState, LoadingButton, Skeleton } from "./ui";

// Credencial oficial (MNI): com ela ativa, a leitura dos autos roda no
// servidor pelo webservice do tribunal — o roteamento escolhe sozinho entre
// MNI e agente por processo. A senha vai direto para o vault e a lista volta
// sempre mascarada.
export default function MniSection({ offline }: { offline: boolean }) {
  const [credenciais, setCredenciais] = useState<MniCredencial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
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
      setError(humanError(err, "Falha ao carregar as credenciais do tribunal"));
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
      setShowForm(false);
      await reload();
      setFeedback("Tribunal conectado pela credencial oficial.");
    } catch {
      setFeedback("Falha ao cadastrar a credencial. Confira os dados do credenciamento.");
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
      setFeedback("Informe um número de processo no campo abaixo para testar.");
      return;
    }
    setBusy(`test-${credencialId}`);
    setFeedback(null);
    try {
      const result = await testarMniCredencial(credencialId, numeroTeste.trim());
      setFeedback(
        result.ok
          ? `Conexão ok — ${result.documentos ?? 0} documento(s) listados.`
          : mniErrorMessage(result.error_code)
      );
      await reload();
    } catch {
      setFeedback("Falha ao testar a conexão com o tribunal.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Credencial oficial do tribunal</span>
      <small className="settingsHint vaultHint">
        <FileSearch size={13} />
        Recomendada: com ela ativa, a leitura dos autos roda no servidor — sem
        depender do computador do advogado. Obtida no credenciamento junto ao
        tribunal; a senha vai direto para o cofre.
      </small>

      <div className="vaultList">
        <AsyncState
          loading={loading}
          error={error}
          empty={!credenciais.length}
          compactError
          skeleton={<Skeleton height={50} radius={8} />}
          emptyState={
            <small className="settingsHint">
              Nenhum tribunal conectado por credencial ainda.
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

      {credenciais.some((cred) => cred.ativo) ? (
        <div className="settingsRow single">
          <label>
            Processo para teste
            <input
              value={numeroTeste}
              disabled={offline}
              onChange={(event) => setNumeroTeste(event.target.value)}
              placeholder="número CNJ usado pelo botão Testar"
            />
          </label>
        </div>
      ) : null}

      <button
        type="button"
        className={`settingsAdvancedToggle${showForm ? "" : " collapsed"}`}
        onClick={() => setShowForm((atual) => !atual)}
      >
        Conectar novo tribunal
        <ChevronDown size={14} />
      </button>

      {showForm ? (
        <>
          <div className="settingsRow duo">
            <label>
              Tribunal
              <input
                value={tribunal}
                disabled={offline}
                onChange={(event) => setTribunal(event.target.value)}
                placeholder="TJMG"
              />
            </label>
            <label>
              Id consultante
              <input
                value={idConsultante}
                disabled={offline}
                onChange={(event) => setIdConsultante(event.target.value)}
                placeholder="CPF/CNPJ do credenciamento"
              />
            </label>
          </div>
          <div className="settingsRow single">
            <label>
              Senha
              <input
                type="password"
                value={senha}
                disabled={offline}
                onChange={(event) => setSenha(event.target.value)}
              />
            </label>
          </div>
          <LoadingButton
            className="toolbarButton primary compact vaultSubmit"
            disabled={offline || !tribunal.trim() || !idConsultante.trim() || !senha}
            loading={busy === "create"}
            icon={<FileSearch size={14} />}
            onClick={() => void cadastrar()}
          >
            Cadastrar
          </LoadingButton>
        </>
      ) : null}

      {feedback ? (
        <small className="settingsHint" role="status">
          {feedback}
        </small>
      ) : null}
    </div>
  );
}
