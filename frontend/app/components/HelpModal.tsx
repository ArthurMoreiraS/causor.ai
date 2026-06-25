"use client";

import { X } from "lucide-react";
import type { ConnectorStatus } from "@/lib/api";
import { connectorStatusLabel } from "@/lib/format";
import { Modal } from "./ui";

export default function HelpModal({
  connectors,
  onClose
}: {
  connectors: ConnectorStatus[];
  onClose: () => void;
}) {
  return (
    <Modal onClose={onClose} labelledBy="helpModalTitle" className="settingsCard">
        <header className="settingsHeader">
          <h3 id="helpModalTitle">Ajuda</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="settingsGroup">
          <span className="settingsLabel">Como funciona</span>
          <ol className="helpSteps">
            <li><strong>Captura por OAB</strong> — puxa intimações do DJEN e metadados do DataJud.</li>
            <li><strong>Prazo</strong> — calculado por motor determinístico (dias úteis, feriados, recesso).</li>
            <li><strong>Minuta</strong> — a IA classifica e redige; você revisa.</li>
            <li><strong>Gate OAB</strong> — nada é protocolado sem aprovação humana.</li>
          </ol>
        </div>
        <div className="settingsGroup">
          <span className="settingsLabel">Atalhos</span>
          <ul className="helpShortcuts">
            <li><kbd>Enter</kbd> envia mensagem no Assistente</li>
            <li>Botão <strong>Exportar</strong> baixa a lista atual em CSV</li>
            <li>Botão <strong>Filtros</strong> refina por tribunal, sistema e risco</li>
          </ul>
        </div>
        <div className="settingsGroup">
          <span className="settingsLabel">Conectores</span>
          <div className="connectorGrid compactConnectors">
            {connectors.map((c) => (
              <article className={`connector ${c.status}`} key={c.name}>
                <div>
                  <strong>{c.name}</strong>
                  <span>{c.detail}</span>
                </div>
                <small>{connectorStatusLabel(c.status)}</small>
              </article>
            ))}
          </div>
        </div>
    </Modal>
  );
}
