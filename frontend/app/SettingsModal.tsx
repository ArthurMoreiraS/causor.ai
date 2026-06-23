"use client";

import { ChevronDown, Loader2, RotateCcw, Trash2, X } from "lucide-react";
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
import VaultSection from "./components/VaultSection";

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
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Configurações</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>

        <div className="settingsGroup">
          <span className="settingsLabel">Perfil do software</span>
          {loadingProfile ? (
            <small className="settingsHint">Carregando...</small>
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
              <div className="settingsRow">
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
              <div className="settingsRow">
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
                  <input
                    value={profileForm.oabUf}
                    disabled={offline}
                    maxLength={2}
                    onChange={(e) =>
                      setProfileForm((form) => ({
                        ...form,
                        oabUf: e.target.value.toUpperCase()
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
              <button
                className="toolbarButton primary settingsSaveButton"
                disabled={
                  offline ||
                  savingProfile ||
                  !profileForm.nomeUsuario.trim() ||
                  !profileForm.nomeEscritorio.trim()
                }
                onClick={() => void saveProfile()}
              >
                {savingProfile ? <Loader2 className="spin" size={14} /> : null}
                Salvar perfil
              </button>
            </>
          )}
          {profileError ? <small className="settingsHint vaultError">{profileError}</small> : null}
        </div>

        <div className="settingsGroup">
          <span className="settingsLabel">Captura — padrões</span>
          <div className="settingsRow">
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
              <input
                value={settings.defaultUf}
                maxLength={2}
                onChange={(e) => onUpdate({ defaultUf: e.target.value.toUpperCase() })}
              />
            </label>
          </div>
        </div>

        <VaultSection offline={offline} />

        <div className="settingsGroup">
          <span className="settingsLabel">OABs monitoradas</span>
          {loadingOabs ? (
            <small className="settingsHint">Carregando...</small>
          ) : oabs.length === 0 ? (
            <small className="settingsHint">Nenhuma OAB capturada ainda.</small>
          ) : (
            <div className="modalListRows">
              {oabs.map((oab) => (
                <div className="modalListRow" key={oab.id}>
                  <span>
                    {oab.oab}/{oab.uf}
                  </span>
                  <button
                    className="toolbarButton compact danger"
                    disabled={offline || removingOabId === oab.id}
                    onClick={() => void removeOab(oab)}
                  >
                    {removingOabId === oab.id ? (
                      <Loader2 className="spin" size={14} />
                    ) : (
                      <Trash2 size={14} />
                    )}
                    Remover dados
                  </button>
                </div>
              ))}
            </div>
          )}
          {oabError ? <small className="settingsHint vaultError">{oabError}</small> : null}
        </div>

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
                Limiar de confiança da IA — {Math.round(settings.confidenceThreshold * 100)}%
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(settings.confidenceThreshold * 100)}
                onChange={(e) => onUpdate({ confidenceThreshold: Number(e.target.value) / 100 })}
              />
              <small className="settingsHint">
                Classificações abaixo deste valor são sinalizadas para revisão humana.
              </small>
            </div>
          ) : null}
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
      </div>
    </div>
  );
}
