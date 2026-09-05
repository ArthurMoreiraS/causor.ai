"use client";

import { AlertTriangle, Landmark, RotateCcw, SlidersHorizontal, Radar, UserCog, X } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { Settings } from "@/lib/settings";
import AcessoTribunaisPanel from "./components/AcessoTribunaisPanel";
import AgentSection from "./components/AgentSection";
import VaultSection from "./components/VaultSection";
import CaptureTab from "./components/settings/CaptureTab";
import ProfileTab from "./components/settings/ProfileTab";
import { InfoHint, Modal } from "./components/ui";

type TabId = "perfil" | "captura" | "tribunais" | "avancado";

const TABS: Array<{ id: TabId; label: string; icon: ReactNode; hint: string }> = [
  { id: "perfil", label: "Perfil", icon: <UserCog size={15} />, hint: "Dados do escritório e papel timbrado" },
  { id: "captura", label: "Captura", icon: <Radar size={15} />, hint: "OABs monitoradas e padrões" },
  { id: "tribunais", label: "Tribunais", icon: <Landmark size={15} />, hint: "Como o Causor entra em cada tribunal" },
  { id: "avancado", label: "Avançado", icon: <SlidersHorizontal size={15} />, hint: "Ajustes finos e reset" }
];

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
  const [tab, setTab] = useState<TabId>("perfil");
  const [confirmReset, setConfirmReset] = useState(false);
  const active = TABS.find((item) => item.id === tab) ?? TABS[0];

  return (
    <Modal onClose={onClose} labelledBy="settingsModalTitle" className="settingsCard">
      <header className="settingsHeader">
        <div className="settingsHeaderText">
          <h3 id="settingsModalTitle">Configurações</h3>
          <small>{active.hint}</small>
        </div>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="settingsBody">
        <nav className="settingsNav" aria-label="Seções das configurações">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === tab ? "settingsNavItem active" : "settingsNavItem"}
              aria-current={item.id === tab ? "true" : undefined}
              onClick={() => setTab(item.id)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="settingsPane" role="region" aria-label={active.label}>
          {tab === "perfil" ? (
            <ProfileTab offline={offline} onOabChanged={onOabChanged} />
          ) : null}

          {tab === "captura" ? (
            <CaptureTab
              settings={settings}
              offline={offline}
              onUpdate={onUpdate}
              onOabChanged={onOabChanged}
            />
          ) : null}

          {tab === "tribunais" ? (
            <>
              <p className="settingsLead">
                O Causor entra no tribunal pelo seu computador, com o seu login. Pareie
                uma vez: é o que permite ler os autos e protocolar.
              </p>
              <AcessoTribunaisPanel offline={offline} />
              <AgentSection offline={offline} />
              <VaultSection offline={offline} />
            </>
          ) : null}

          {tab === "avancado" ? (
            <>
              <section className="settingsSection">
                <div className="settingsSectionHead">
                  <h4>
                    Limiar de confiança da IA{" "}
                    <InfoHint label="Quando a confiança da classificação da IA fica abaixo deste limiar, a minuta é sinalizada para revisão humana antes de seguir para aprovação." />
                  </h4>
                  <p>Classificações abaixo deste valor vão para revisão humana.</p>
                </div>
                <div className="settingsSlider">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={Math.round(settings.confidenceThreshold * 100)}
                    aria-label="Limiar de confiança da IA"
                    onChange={(e) => onUpdate({ confidenceThreshold: Number(e.target.value) / 100 })}
                  />
                  <strong>{Math.round(settings.confidenceThreshold * 100)}%</strong>
                </div>
              </section>

              <section className="settingsSection settingsDangerZone">
                <div className="settingsSectionHead">
                  <h4>Restaurar padrões</h4>
                  <p>
                    Devolve as preferências deste navegador ao estado inicial. Não apaga
                    processos, prazos nem credenciais.
                  </p>
                </div>
                <button
                  type="button"
                  className="toolbarButton compact"
                  onClick={() => setConfirmReset(true)}
                >
                  <RotateCcw size={14} />
                  Restaurar padrões
                </button>
              </section>
            </>
          ) : null}
        </div>
      </div>

      <footer className="settingsFooter">
        <button className="toolbarButton primary" onClick={onClose}>
          Concluir
        </button>
      </footer>

      {confirmReset ? (
        <Modal
          onClose={() => setConfirmReset(false)}
          labelledBy="resetConfirmTitle"
          className="confirmCard"
        >
          <div className="confirmIcon danger" aria-hidden="true">
            <AlertTriangle size={18} />
          </div>
          <div className="confirmBody">
            <span className="settingsLabel" id="resetConfirmTitle">
              Restaurar as preferências?
            </span>
            <p>
              OAB padrão, UF e limiar de confiança voltam ao valor inicial. Seus processos,
              prazos e credenciais não são afetados.
            </p>
          </div>
          <div className="modalActions">
            <button
              type="button"
              className="toolbarButton compact"
              onClick={() => setConfirmReset(false)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="toolbarButton compact danger confirmDanger"
              onClick={() => {
                onReset();
                setConfirmReset(false);
              }}
            >
              <RotateCcw size={14} />
              Restaurar
            </button>
          </div>
        </Modal>
      ) : null}
    </Modal>
  );
}
