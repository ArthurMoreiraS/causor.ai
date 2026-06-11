"use client";

import { Monitor, Moon, RotateCcw, Sun, X } from "lucide-react";
import type { Settings, ThemeMode } from "@/lib/settings";

const THEME_OPTIONS: Array<{ value: ThemeMode; label: string; icon: typeof Sun }> = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
  { value: "system", label: "Sistema", icon: Monitor }
];

export default function SettingsModal({
  settings,
  onUpdate,
  onReset,
  onClose
}: {
  settings: Settings;
  onUpdate: (patch: Partial<Settings>) => void;
  onReset: () => void;
  onClose: () => void;
}) {
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
          <span className="settingsLabel">Tema</span>
          <div className="segmented">
            {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                className={settings.theme === value ? "active" : ""}
                onClick={() => onUpdate({ theme: value })}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="settingsGroup">
          <span className="settingsLabel">Densidade da interface</span>
          <div className="segmented">
            <button
              className={settings.density === "confortavel" ? "active" : ""}
              onClick={() => onUpdate({ density: "confortavel" })}
            >
              Confortável
            </button>
            <button
              className={settings.density === "compacta" ? "active" : ""}
              onClick={() => onUpdate({ density: "compacta" })}
            >
              Compacta
            </button>
          </div>
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

        <div className="settingsGroup">
          <span className="settingsLabel">Calendário forense</span>
          <label className="settingsInline">
            Anos considerados na contagem de prazos
            <input
              type="number"
              min={1}
              max={6}
              value={settings.calendarYears}
              onChange={(e) =>
                onUpdate({ calendarYears: Math.max(1, Math.min(6, Number(e.target.value) || 1)) })
              }
            />
          </label>
        </div>

        <div className="settingsGroup">
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
