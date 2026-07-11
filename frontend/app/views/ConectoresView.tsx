"use client";

import { LockKeyhole, ShieldCheck } from "lucide-react";
import { ConnectorStatus } from "@/lib/api";
import { connectorStatusLabel } from "@/lib/format";

const CONNECTOR_NOTES: Record<string, string> = {
  djen: "Captura oficial de intimações via Comunica/DJEN — sem scraping.",
  datajud: "Metadados e movimentos de processo via API pública do CNJ.",
  pje: "Protocolo assistido: prepara peça, anexos e checkpoint ready_to_sign; assinatura e envio final seguem no PJe/PJeOffice.",
  esaj: "Próximo conector após o piloto PJe."
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
        {connectors.map((connector) => (
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
            <strong>APIs oficiais antes de scraping</strong>
            <span>
              A captura usa DJEN/Comunica e DataJud. Automação de portal (Playwright) é reservada
              para a ação de protocolo, sempre com fallback humano.
            </span>
          </div>
        </article>
        <article className="securityCard clickable" onClick={onOpenVault}>
          <LockKeyhole size={18} />
          <div>
            <strong>Acesso aos tribunais</strong>
            <span>
              O login do tribunal roda no computador do advogado (agente local) e nunca sai
              dele; o Causor guarda só o estado “conectado”. Gerencie em Configurações →
              Acesso aos tribunais.
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}
