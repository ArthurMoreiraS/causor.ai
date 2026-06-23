"use client";

import { AlertTriangle, LockKeyhole, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { CredencialAssinatura, listarCredenciais, Peticao, Processo } from "@/lib/api";
import SearchSelect from "./SearchSelect";
import { LoadingButton, Modal, Skeleton } from "./ui";

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
  onConfirm: (credencialId: number | null) => void;
  onClose: () => void;
}) {
  const [credenciais, setCredenciais] = useState<CredencialAssinatura[]>([]);
  const [credencialId, setCredencialId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const isPje = processo?.sistema?.toLowerCase() === "pje";
  const credencialOptions = credenciais.map((credencial) => ({
    value: String(credencial.id),
    label: `${credencial.provedor} (${credencial.modo}) - vault #${credencial.id}`,
    detail: `${credencial.provedor} (${credencial.modo}) - vault #${credencial.id}`,
    searchText: `${credencial.provedor} ${credencial.modo} vault ${credencial.id}`
  }));

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ativas = (await listarCredenciais()).filter((c) => c.ativo);
        if (cancelled) return;
        setCredenciais(ativas);
        setCredencialId(ativas[0]?.id ?? null);
      } catch {
        if (!cancelled) setCredenciais([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
          {isPje ? (
            <span>
              O Causor prepara o protocolo PJe assistido e para em{" "}
              <strong>ready_to_sign</strong>. A assinatura/envio final acontece no PJe/PJeOffice;
              depois registre o número do protocolo.
            </span>
          ) : (
            <span>
              O protocolo é o ato irreversível do fluxo. Para sistemas sem conector dedicado, o
              Causor registra a execução operacional com gate e auditoria.
            </span>
          )}
        </div>

        <label className="protocolarCredencial">
          Credencial de assinatura
          {loading ? (
            <Skeleton height={34} radius={9} />
          ) : credenciais.length ? (
            <SearchSelect
              value={String(credencialId ?? credenciais[0]?.id ?? "")}
              options={credencialOptions}
              onChange={(value) => setCredencialId(Number(value))}
            />
          ) : (
            <span className="protocolarHint">
              <LockKeyhole size={13} /> Nenhuma credencial ativa no vault. No PJe assistido, o
              advogado pode assinar manualmente no PJe/PJeOffice.
            </span>
          )}
        </label>

        <div className="modalActions">
          <button className="toolbarButton" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <LoadingButton
            className="toolbarButton primary"
            loading={busy}
            icon={<Send size={15} />}
            disabled={busy}
            onClick={() => onConfirm(credencialId)}
          >
            {isPje ? "Preparar no PJe" : "Registrar protocolo"}
          </LoadingButton>
        </div>
    </Modal>
  );
}
