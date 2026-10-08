"use client";

import { X } from "lucide-react";
import type { ConnectorStatus } from "@/lib/api";
import { connectorStatusLabel } from "@/lib/format";
import { Modal } from "./ui";

const STEPS: Array<[string, string]> = [
  ["Captura por OAB", "Puxa as intimações do DJEN e os metadados do DataJud."],
  ["Prazo", "Calculado por motor determinístico, com dias úteis, feriados e recesso."],
  ["Documentos e trabalhos", "Reúna os autos e os documentos do cliente, declare o que falta e registre a providência."],
  ["Minuta", "Confira fatos, páginas citadas e alertas antes de usar o texto."],
  ["Revisão e aprovação", "Salve a versão revisada; um advogado aprova antes de a peça sair do Causor."],
  ["Clientes", "Cadastre a parte representada, vincule os processos e crie tarefas de atendimento."],
  ["Tarefas e equipe", "Distribua providências com responsável. Convide a equipe em Configurações → Equipe."]
];

const STATUS_TONE: Record<string, string> = { online: "ok", live: "ok", pilot: "warn", validation: "warn" };

export default function HelpModal({
  connectors,
  onClose
}: {
  connectors: ConnectorStatus[];
  onClose: () => void;
}) {
  const sources = connectors.filter((c) => c.key === "djen" || c.key === "datajud");
  return (
    <Modal onClose={onClose} labelledBy="helpModalTitle" className="infoCard">
      <header className="settingsHeader">
        <div className="settingsHeaderText">
          <h3 id="helpModalTitle">Ajuda</h3>
          <small>Do aviso publicado à minuta revisada.</small>
        </div>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="infoBody">
        <section className="infoSection">
          <h4>Como funciona</h4>
          <ol className="helpSteps">
            {STEPS.map(([title, text], index) => (
              <li key={title}>
                <span className="helpStepNumber" aria-hidden="true">{index + 1}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="infoSection">
          <h4>Atalhos</h4>
          <ul className="helpShortcuts">
            <li><kbd>Enter</kbd><span>envia a mensagem no Assistente</span></li>
            <li><kbd>Esc</kbd><span>fecha a janela aberta</span></li>
            <li><strong>Exportar</strong><span>baixa a lista atual em CSV</span></li>
            <li><strong>Filtros</strong><span>refina por tribunal, sistema e risco</span></li>
          </ul>
        </section>

        {sources.length ? (
          <section className="infoSection">
            <h4>Fontes de captura</h4>
            <div className="modalListRows">
              {sources.map((c) => (
                <div className="modalListRow" key={c.key}>
                  <div className="infoRowText">
                    <span>{c.name}</span>
                    <small className="settingsHint">{c.detail}</small>
                  </div>
                  <span className={`statusBadge ${STATUS_TONE[c.status] ?? ""}`}>
                    {connectorStatusLabel(c.status)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>

      <footer className="settingsFooter">
        <button className="toolbarButton primary" onClick={onClose}>
          Entendi
        </button>
      </footer>
    </Modal>
  );
}
