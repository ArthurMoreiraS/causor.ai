"use client";

import { CalendarDays, X } from "lucide-react";
import { useState } from "react";
import type { Prazo } from "@/lib/api";

export type PrazoPatch = Partial<
  Pick<Prazo, "descricao" | "dias" | "dias_uteis" | "data_inicio" | "data_fatal">
>;

export default function PrazoEditModal({
  prazo,
  busy,
  onSave,
  onClose
}: {
  prazo: Prazo;
  busy: boolean;
  onSave: (patch: PrazoPatch) => void;
  onClose: () => void;
}) {
  const [descricao, setDescricao] = useState(prazo.descricao ?? "");
  const [dataFatal, setDataFatal] = useState(prazo.data_fatal);
  const [dias, setDias] = useState(prazo.dias);
  const [diasUteis, setDiasUteis] = useState(prazo.dias_uteis);

  function submit() {
    const patch: PrazoPatch = {};
    if (descricao !== (prazo.descricao ?? "")) patch.descricao = descricao;
    if (dataFatal !== prazo.data_fatal) patch.data_fatal = dataFatal;
    if (dias !== prazo.dias) patch.dias = dias;
    if (diasUteis !== prazo.dias_uteis) patch.dias_uteis = diasUteis;
    onSave(patch);
  }

  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Revisar prazo</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>

        <div className="settingsGroup">
          <span className="settingsLabel">Descrição</span>
          <input
            className="fieldInput"
            value={descricao}
            placeholder="Ex.: Contestação"
            onChange={(e) => setDescricao(e.target.value)}
          />
        </div>

        <div className="settingsRow">
          <label>
            Data fatal
            <input type="date" value={dataFatal} onChange={(e) => setDataFatal(e.target.value)} />
          </label>
          <label>
            Dias
            <input
              type="number"
              min={1}
              value={dias}
              onChange={(e) => setDias(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
        </div>

        <label className="settingsInline">
          Contagem em dias úteis (CPC art. 219)
          <input
            type="checkbox"
            checked={diasUteis}
            onChange={(e) => setDiasUteis(e.target.checked)}
          />
        </label>

        <small className="settingsHint">
          A revisão é registrada na trilha de auditoria imutável.
        </small>

        <footer className="settingsFooter">
          <button className="toolbarButton compact" onClick={onClose}>
            Cancelar
          </button>
          <button className="toolbarButton primary" onClick={submit} disabled={busy}>
            <CalendarDays size={14} />
            Salvar revisão
          </button>
        </footer>
      </div>
    </div>
  );
}
