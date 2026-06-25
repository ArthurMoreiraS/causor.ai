"use client";

import { ChevronDown, RotateCcw, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  atualizarPerfilOperacional,
  carregarPerfilOperacional,
  listarOabsMonitoradas,
  OabMonitorada,
  OperationalProfile,
  removerOabMonitorada
} from "@/lib/api";
import type { Settings } from "@/lib/settings";
import UfSearchSelect from "./components/UfSearchSelect";
import VaultSection from "./components/VaultSection";
import { useToast } from "./components/Toast";
import { InfoHint, LoadingButton, Modal, Skeleton } from "./components/ui";

export default function SettingsModal({
  settings,
  offline,
  onUpdate,
  onReset,
  onOabChanged,
  onClose
}: {
  settings: Settings;
  offline: boolean;
  onUpdate: (patch: Partial<Settings>) => void;
  onReset: () => void;
  onOabChanged: () => Promise<void>;
  onClose: () => void;
}) {
  const toast = useToast();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [oabs, setOabs] = useState<OabMonitorada[]>([]);
  const [loadingOabs, setLoadingOabs] = useState(true);
  const [removingOabId, setRemovingOabId] = useState<number | null>(null);
  const [oabError, setOabError] = useState<string | null>(null);
  const [profile, setProfile] = useState<OperationalProfile | null>(null);
  const [profileForm, setProfileForm] = useState({
    nomeUsuario: "",
    nomeEscritorio: "",
    cnpj: "",
    oab: "",
    oabUf: "SP"
  });
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  async function loadProfile() {
    if (offline) {
      setLoadingProfile(false);
      return;
    }
    setLoadingProfile(true);
    try {
      const nextProfile = await carregarPerfilOperacional();
      setProfile(nextProfile);
      setProfileForm({
        nomeUsuario: nextProfile.usuario.nome,
        nomeEscritorio: nextProfile.escritorio.nome,
        cnpj: nextProfile.escritorio.cnpj ?? "",
        oab: nextProfile.usuario.oab ?? "",
        oabUf: nextProfile.usuario.oab_uf ?? "SP"
      });
      setProfileError(null);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Falha ao carregar perfil");
    } finally {
      setLoadingProfile(false);
    }
  }

  async function saveProfile() {
    setSavingProfile(true);
    try {
      const updated = await atualizarPerfilOperacional({
        nome_usuario: profileForm.nomeUsuario.trim(),
        nome_escritorio: profileForm.nomeEscritorio.trim(),
        cnpj: profileForm.cnpj.trim() || null,
        oab: profileForm.oab.trim() || null,
        oab_uf: profileForm.oabUf.trim().toUpperCase() || null
      });
      setProfile(updated);
      setProfileForm({
        nomeUsuario: updated.usuario.nome,
        nomeEscritorio: updated.escritorio.nome,
        cnpj: updated.escritorio.cnpj ?? "",
        oab: updated.usuario.oab ?? "",
        oabUf: updated.usuario.oab_uf ?? "SP"
      });
      setProfileError(null);
      await onOabChanged();
      toast({ kind: "success", title: "Perfil salvo" });
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Perfil nao salvo");
    } finally {
      setSavingProfile(false);
    }
  }

  async function loadOabs() {
    if (offline) {
      setOabs([]);
      setLoadingOabs(false);
      return;
    }
    setLoadingOabs(true);
    try {
      setOabs(await listarOabsMonitoradas());
      setOabError(null);
    } catch (err) {
      setOabError(err instanceof Error ? err.message : "Falha ao carregar OABs");
    } finally {
      setLoadingOabs(false);
    }
  }

  async function removeOab(oab: OabMonitorada) {
    const confirmed = window.confirm(
      `Remover OAB ${oab.oab}/${oab.uf} e apagar intimações, prazos, processos e petições capturados por ela?`
    );
    if (!confirmed) return;
    setRemovingOabId(oab.id);
    try {
      await removerOabMonitorada(oab.id, true);
      await loadOabs();
      await onOabChanged();
      setOabError(null);
      toast({ kind: "success", title: `OAB ${oab.oab}/${oab.uf} removida`, description: "Dados capturados por ela foram apagados." });
    } catch (err) {
      setOabError(err instanceof Error ? err.message : "OAB não removida");
    } finally {
      setRemovingOabId(null);
    }
  }

  useEffect(() => {
    void loadProfile();
    void loadOabs();
  }, [offline]);

  return (
    <Modal
      onClose={onClose}
      labelledBy="settingsModalTitle"
      className="settingsCard settingsCardWide"
    >
      <header className="settingsHeader">
        <h3 id="settingsModalTitle">Configurações</h3>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="settingsLayout">
        <div className="settingsGroup">
          <span className="settingsLabel">Perfil do software</span>
          {loadingProfile ? (
            <div className="skeletonGroup" aria-hidden="true">
              <Skeleton height={40} radius={6} />
              <Skeleton height={40} radius={6} />
              <Skeleton height={40} radius={6} />
            </div>
          ) : (
            <>
              <div className="settingsRow single">
                <label>
                  Nome do usuario
                  <input
                    value={profileForm.nomeUsuario}
                    disabled={offline}
                    onChange={(e) =>
                      setProfileForm((form) => ({ ...form, nomeUsuario: e.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="settingsRow duo">
                <label>
                  Nome do escritorio
                  <input
                    value={profileForm.nomeEscritorio}
                    disabled={offline}
                    onChange={(e) =>
                      setProfileForm((form) => ({ ...form, nomeEscritorio: e.target.value }))
                    }
                  />
                </label>
                <label>
                  CNPJ
                  <input
                    value={profileForm.cnpj}
                    disabled={offline}
                    placeholder="Opcional"
                    onChange={(e) =>
                      setProfileForm((form) => ({ ...form, cnpj: e.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="settingsRow ufRow">
                <label>
                  OAB do usuario
                  <input
                    value={profileForm.oab}
                    disabled={offline}
                    placeholder="Numero"
                    onChange={(e) =>
                      setProfileForm((form) => ({ ...form, oab: e.target.value }))
                    }
                  />
                </label>
                <label>
                  UF
                  <UfSearchSelect
                    value={profileForm.oabUf}
                    disabled={offline}
                    name="oab_uf"
                    onChange={(uf) =>
                      setProfileForm((form) => ({
                        ...form,
                        oabUf: uf
                      }))
                    }
                  />
                </label>
              </div>
              {profile ? (
                <small className="settingsHint">
                  Conta conectada: {profile.usuario.email}
                </small>
              ) : null}
              <LoadingButton
                className="toolbarButton primary settingsSaveButton"
                loading={savingProfile}
                disabled={
                  offline ||
                  !profileForm.nomeUsuario.trim() ||
                  !profileForm.nomeEscritorio.trim()
                }
                onClick={() => void saveProfile()}
              >
                Salvar perfil
              </LoadingButton>
            </>
          )}
          {profileError ? (
            <small className="settingsHint vaultError">{profileError}</small>
          ) : null}
        </div>

        <div className="settingsColumns">
          <div className="settingsColumn">
            <div className="settingsGroup">
              <span className="settingsLabel">Captura — padrões</span>
              <div className="settingsRow ufRow">
                <label>
                  OAB padrão
                  <input
                    value={settings.defaultOab}
                    placeholder="Número da OAB"
                    onChange={(e) => onUpdate({ defaultOab: e.target.value })}
                  />
                </label>
                <label>
                  UF
                  <UfSearchSelect
                    value={settings.defaultUf}
                    disabled={offline}
                    name="default_uf"
                    onChange={(uf) => onUpdate({ defaultUf: uf })}
                  />
                </label>
              </div>
            </div>

            <div className="settingsGroup">
              <span className="settingsLabel">OABs monitoradas</span>
              {loadingOabs ? (
                <div className="skeletonGroup" aria-hidden="true">
                  <Skeleton height={38} radius={6} />
                  <Skeleton height={38} radius={6} />
                </div>
              ) : oabs.length === 0 ? (
                <small className="settingsHint">Nenhuma OAB capturada ainda.</small>
              ) : (
                <div className="modalListRows">
                  {oabs.map((oab) => (
                    <div className="modalListRow" key={oab.id}>
                      <span>
                        {oab.oab}/{oab.uf}
                      </span>
                      <LoadingButton
                        className="toolbarButton compact danger"
                        disabled={offline}
                        loading={removingOabId === oab.id}
                        icon={<Trash2 size={14} />}
                        onClick={() => void removeOab(oab)}
                      >
                        Remover dados
                      </LoadingButton>
                    </div>
                  ))}
                </div>
              )}
              {oabError ? (
                <small className="settingsHint vaultError">{oabError}</small>
              ) : null}
            </div>
          </div>

          <div className="settingsColumn">
            <VaultSection offline={offline} />

            <div className="settingsGroup">
              <button
                type="button"
                className={`settingsAdvancedToggle${showAdvanced ? "" : " collapsed"}`}
                aria-expanded={showAdvanced}
                onClick={() => setShowAdvanced((value) => !value)}
              >
                <span>Avançado</span>
                <ChevronDown size={14} />
              </button>
              {showAdvanced ? (
                <div className="settingsAdvancedBody">
                  <span className="settingsLabel">
                    Limiar de confiança da IA — {Math.round(settings.confidenceThreshold * 100)}%{" "}
                    <InfoHint label="Quando a confiança da classificação da IA fica abaixo deste limiar, a minuta é sinalizada para revisão humana antes de seguir para o Gate OAB." />
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={Math.round(settings.confidenceThreshold * 100)}
                    onChange={(e) =>
                      onUpdate({ confidenceThreshold: Number(e.target.value) / 100 })
                    }
                  />
                  <small className="settingsHint">
                    Classificações abaixo deste valor são sinalizadas para revisão humana.
                  </small>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <footer className="settingsFooter">
        <button className="toolbarButton compact" onClick={onReset}>
          <RotateCcw size={14} />
          Restaurar padrões
        </button>
        <button className="toolbarButton primary" onClick={onClose}>
          Concluir
        </button>
      </footer>
    </Modal>
  );
}
