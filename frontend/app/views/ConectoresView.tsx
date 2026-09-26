"use client";

import { LockKeyhole, ShieldCheck } from "lucide-react";
import { ConnectorStatus } from "@/lib/api";
import { connectorStatusLabel } from "@/lib/format";

const CONNECTOR_NOTES: Record<string, string> = {
  djen: "Captura oficial de intimações via Comunica/DJEN — sem scraping.",
  datajud: "Metadados e movimentos de processo via API pública do CNJ."
};

export default function ConectoresView({
  connectors,
  onOpenVault
}: {
  connectors: ConnectorStatus[];
  onOpenVault: () => void;
}) {
  return (
    <section className="connectorsSurface">
      <div className="connectorGrid large">
        {connectors.filter(connector => connector.key === "djen" || connector.key === "datajud").map((connector) => (
          <article className={`connector ${connector.status}`} key={connector.key}>
            <div>
              <strong>{connector.name}</strong>
              <span>{connector.detail}</span>
              <p className="connectorNote">{CONNECTOR_NOTES[connector.key] ?? ""}</p>
            </div>
            <small>{connectorStatusLabel(connector.status)}</small>
          </article>
        ))}
      </div>

      <div className="connectorsSecurity">
        <article className="securityCard">
          <ShieldCheck size={18} />
          <div>
            <strong>Fontes com escopo definido</strong>
            <span>
              DJEN/Comunica traz publicações e DataJud traz metadados. Nenhuma das duas
              fontes comprova o inteiro teor dos autos; documentos recebidos exigem
              conferência de origem e cobertura.
            </span>
          </div>
        </article>
        <article className="securityCard clickable" onClick={onOpenVault}>
          <LockKeyhole size={18} />
          <div>
            <strong>Acesso aos tribunais</strong>
            <span>
              Leitura e envio dependem de uma rota autorizada para o tribunal e a
              instância do caso. Consulte o estado em Configurações → Tribunais;
              parear um computador, sozinho, não comprova essa capacidade.
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}
