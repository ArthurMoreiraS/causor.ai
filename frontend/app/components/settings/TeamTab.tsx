"use client";

import { useCallback, useEffect, useState } from "react";
import { MailPlus, Send, UserCheck, UserX } from "lucide-react";
import {
  alterarMembro,
  convidarMembro,
  listarUsuarios,
  reenviarConvite,
  type Papel,
  type ResultadoConvite,
  type Usuario
} from "@/lib/api";
import { humanError, mensagemDoServidor } from "@/lib/errors";
import { PAPEIS, PAPEL_DESCRICAO, PAPEL_LABEL, usePermissoes } from "@/lib/permissoes";
import { useToast } from "../Toast";
import { AsyncState, LoadingButton, Skeleton } from "../ui";

const MENSAGEM_CONVITE: Record<ResultadoConvite, (email: string) => { title: string; description?: string }> = {
  enviado: (email) => ({ title: "Convite enviado", description: `${email} recebe um e-mail para definir a senha.` }),
  ja_cadastrado: (email) => ({
    title: "Membro adicionado",
    description: `${email} já tem conta de acesso: entra com a senha que tem ou pelo "Esqueci minha senha".`
  }),
  manual: (email) => ({
    title: "Membro adicionado",
    description: `O envio automático não está configurado. Convide ${email} pelo painel do Supabase (Authentication → Users → Invite).`
  })
};

function situacao(membro: Usuario): { label: string; tone: string } {
  if (!membro.ativo) return { label: "Desativado", tone: "" };
  if (membro.convite_pendente) return { label: "Convite pendente", tone: "warn" };
  return { label: "Ativo", tone: "ok" };
}

// Equipe do escritório. Todos veem quem faz parte; só o administrador convida,
// muda papel e desativa. Desativar não apaga: autoria e auditoria ficam.
export default function TeamTab({ offline }: { offline: boolean }) {
  const toast = useToast();
  const { me, pode } = usePermissoes(!offline);
  const gerir = Boolean(me) && pode("gerir_equipe");
  const [membros, setMembros] = useState<Usuario[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [form, setForm] = useState<{ nome: string; email: string; papel: Papel }>({
    nome: "",
    email: "",
    papel: "advogado"
  });
  const [inviting, setInviting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (offline) {
      setLoading(false);
      return;
    }
    try {
      setMembros(await listarUsuarios());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Não foi possível carregar a equipe"));
    } finally {
      setLoading(false);
    }
  }, [offline]);

  useEffect(() => {
    void load();
  }, [load]);

  function substituir(atualizado: Usuario) {
    setMembros((lista) => lista.map((m) => (m.id === atualizado.id ? atualizado : m)));
  }

  async function convidar() {
    setInviting(true);
    setFormError(null);
    try {
      const { membro, convite } = await convidarMembro({
        nome: form.nome.trim(),
        email: form.email.trim(),
        papel: form.papel
      });
      setMembros((lista) => [...lista, membro]);
      setForm({ nome: "", email: "", papel: form.papel });
      toast({ kind: "success", ...MENSAGEM_CONVITE[convite](membro.email ?? form.email) });
    } catch (err) {
      setFormError(mensagemDoServidor(err) ?? humanError(err, "O convite não foi enviado"));
    } finally {
      setInviting(false);
    }
  }

  async function agir(membro: Usuario, acao: () => Promise<void>, falha: string) {
    setBusyId(membro.id);
    setError(null);
    try {
      await acao();
    } catch (err) {
      setError(mensagemDoServidor(err) ?? humanError(err, falha));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <section className="settingsSection">
        <div className="settingsSectionHead">
          <h4>Membros do escritório</h4>
          <p>
            Todos veem os processos, prazos e tarefas do escritório. O papel define quem aprova
            minutas, altera prazos e cuida da configuração.
          </p>
        </div>
        <AsyncState
          loading={loading}
          error={error}
          empty={!membros.length}
          compactError
          skeleton={
            <div className="skeletonGroup" aria-hidden="true">
              <Skeleton height={38} radius={6} />
              <Skeleton height={38} radius={6} />
            </div>
          }
          emptyState={<small className="settingsHint">Nenhum membro encontrado.</small>}
          retrying={retrying}
          onRetry={() => {
            setRetrying(true);
            void load().finally(() => setRetrying(false));
          }}
        >
          <div className="modalListRows">
            {membros.map((membro) => {
              const status = situacao(membro);
              const eu = membro.id === me?.usuario_id;
              const editavel = gerir && !eu && !offline;
              return (
                <div className="modalListRow teamRow" key={membro.id}>
                  <div className="teamMember">
                    <span>
                      {membro.nome}
                      {eu ? " (você)" : ""}
                    </span>
                    <small className="settingsHint">{membro.email}</small>
                  </div>
                  <div className="teamActions">
                    <span className={`statusBadge ${status.tone}`}>{status.label}</span>
                    {editavel && membro.ativo ? (
                      <label className="selectControl">
                        <span className="sr-only">Papel de {membro.nome}</span>
                        <select
                          value={membro.papel}
                          disabled={busyId !== null}
                          onChange={(e) => {
                            const papel = e.target.value as Papel;
                            void agir(membro, async () => substituir(await alterarMembro(membro.id, { papel })),
                              "O papel não foi alterado");
                          }}
                        >
                          {PAPEIS.map((papel) => (
                            <option key={papel} value={papel}>{PAPEL_LABEL[papel]}</option>
                          ))}
                        </select>
                      </label>
                    ) : (
                      <span className="statusBadge">{PAPEL_LABEL[membro.papel]}</span>
                    )}
                    {editavel && membro.ativo && membro.convite_pendente ? (
                      <LoadingButton
                        className="toolbarButton compact"
                        loading={busyId === membro.id}
                        disabled={busyId !== null}
                        icon={<Send size={14} />}
                        onClick={() =>
                          void agir(membro, async () => {
                            const { convite } = await reenviarConvite(membro.id);
                            toast({ kind: "success", ...MENSAGEM_CONVITE[convite](membro.email ?? "") });
                          }, "O convite não foi reenviado")
                        }
                      >
                        Reenviar
                      </LoadingButton>
                    ) : null}
                    {editavel ? (
                      <LoadingButton
                        className={membro.ativo ? "toolbarButton compact danger" : "toolbarButton compact"}
                        loading={busyId === membro.id}
                        disabled={busyId !== null}
                        icon={membro.ativo ? <UserX size={14} /> : <UserCheck size={14} />}
                        onClick={() =>
                          void agir(membro, async () => substituir(await alterarMembro(membro.id, { ativo: !membro.ativo })),
                            membro.ativo ? "O membro não foi desativado" : "O membro não foi reativado")
                        }
                      >
                        {membro.ativo ? "Desativar" : "Reativar"}
                      </LoadingButton>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </AsyncState>
        {me && !gerir ? (
          <small className="settingsHint">Só administradores convidam, mudam papéis e desativam membros.</small>
        ) : null}
      </section>

      {gerir ? (
        <section className="settingsSection">
          <div className="settingsSectionHead">
            <h4>Convidar membro</h4>
            <p>A pessoa recebe um e-mail para definir a senha e entra direto no escritório.</p>
          </div>
          <div className="settingsRow duo">
            <label>
              Nome
              <input
                value={form.nome}
                disabled={offline}
                onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              />
            </label>
            <label>
              E-mail
              <input
                type="email"
                value={form.email}
                disabled={offline}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </label>
          </div>
          <div className="settingsRow single">
            <label>
              Papel
              <select
                value={form.papel}
                disabled={offline}
                onChange={(e) => setForm((f) => ({ ...f, papel: e.target.value as Papel }))}
              >
                {PAPEIS.map((papel) => (
                  <option key={papel} value={papel}>{PAPEL_LABEL[papel]}</option>
                ))}
              </select>
            </label>
            <small className="settingsHint">{PAPEL_DESCRICAO[form.papel]}</small>
          </div>
          <div className="settingsSectionFoot">
            <LoadingButton
              className="toolbarButton primary"
              loading={inviting}
              disabled={offline || form.nome.trim().length < 2 || !form.email.includes("@")}
              icon={<MailPlus size={14} />}
              onClick={() => void convidar()}
            >
              Enviar convite
            </LoadingButton>
          </div>
          {formError ? (
            <small className="settingsHint vaultError" role="alert">
              {formError}
            </small>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
