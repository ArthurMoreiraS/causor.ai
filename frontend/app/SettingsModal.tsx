"use client";

import { ChevronDown, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import type { Settings } from "@/lib/settings";
import VaultSection from "./components/VaultSection";

export default function SettingsModal({
  settings,
  offline,
  onUpdate,
  onReset,
  onClose
}: {
  settings: Settings;
  offline: boolean;
  onUpdate: (patch: Partial<Settings>) => void;
  onReset: () => void;
  onClose: () => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);

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
