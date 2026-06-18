"use client";

import { AlertTriangle, Loader2, LockKeyhole, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { CredencialAssinatura, listarCredenciais, Peticao, Processo } from "@/lib/api";

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
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard" onClick={(e) => e.stopPropagation()}>
        <h3>Protocolar petição</h3>
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
            <span className="protocolarHint">
              <Loader2 className="spin" size={13} /> carregando credenciais...
            </span>
          ) : credenciais.length ? (
            <select
              value={credencialId ?? ""}
              onChange={(e) => setCredencialId(e.target.value ? Number(e.target.value) : null)}
            >
              {credenciais.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.provedor} ({c.modo}) - vault #{c.id}
                </option>
              ))}
            </select>
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
          <button
            className="toolbarButton primary"
            disabled={busy}
            onClick={() => onConfirm(credencialId)}
          >
            {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
            {isPje ? "Preparar no PJe" : "Registrar protocolo"}
          </button>
        </div>
      </div>
    </div>
  );
}
