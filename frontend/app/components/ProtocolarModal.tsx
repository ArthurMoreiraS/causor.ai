"use client";

import { AlertTriangle, Send } from "lucide-react";
import { Peticao, Processo } from "@/lib/api";
import { LoadingButton, Modal } from "./ui";

export default function ProtocolarModal({
  peticao,
  processo,
  busy,
  onConfirm,
  onClose
}: {
  peticao: Peticao;
  processo: Processo | null;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const sistema = processo?.sistema?.trim() || null;

  return (
    <Modal onClose={onClose} labelledBy="protocolarModalTitle">
      <h3 id="protocolarModalTitle">Protocolar petição</h3>
      <p className="protocolarResumo">
        <strong>{peticao.tipo ?? "Petição"}</strong>
        {" - processo "}
        <span className="mono">{processo?.numero ?? `#${peticao.processo_id}`}</span>
      </p>

      <div className="protocolarAviso">
        <AlertTriangle size={16} />
        <span>
          O envio pelo executor depende de uma integração disponível para este tribunal.
          A solicitação só será concluída quando houver confirmação do resultado.
          Se a integração estiver indisponível, baixe o PDF aprovado, envie no tribunal
          e registre o resultado em Protocolos. Conectar o computador não habilita
          automaticamente leitura ou envio.
        </span>
      </div>

      {sistema ? (
        <p className="protocolarHint">
          Destino: <strong>{sistema}</strong>
          {processo?.tribunal ? (
            <>
              {" · "}
              <span className="mono">{processo.tribunal}</span>
            </>
          ) : null}
        </p>
      ) : (
        <p className="protocolarHint">
          Sistema do processo não identificado — o Causor tentará resolver pelo tribunal.
        </p>
      )}

      <div className="modalActions">
        <button className="toolbarButton" onClick={onClose} disabled={busy}>
          Cancelar
        </button>
        <LoadingButton
          className="toolbarButton primary"
          loading={busy}
          icon={<Send size={15} />}
          disabled={busy}
          onClick={() => onConfirm()}
        >
          Solicitar envio pela integração
        </LoadingButton>
      </div>
    </Modal>
  );
}
