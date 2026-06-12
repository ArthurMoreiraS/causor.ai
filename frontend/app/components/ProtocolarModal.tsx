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
          {" — processo "}
          <span className="mono">{processo?.numero ?? `#${peticao.processo_id}`}</span>
        </p>

        <div className="protocolarAviso">
          <AlertTriangle size={16} />
          <span>
            O protocolo é o ato irreversível do fluxo. Esta execução é{" "}
            <strong>simulada</strong> — conector PJe em desenvolvimento — mas o gate e a
            auditoria funcionam como no fluxo real.
          </span>
        </div>

        <label className="protocolarCredencial">
          Credencial de assinatura
          {loading ? (
            <span className="protocolarHint">
              <Loader2 className="spin" size={13} /> carregando credenciais…
            </span>
          ) : credenciais.length ? (
            <select
              value={credencialId ?? ""}
              onChange={(e) => setCredencialId(e.target.value ? Number(e.target.value) : null)}
            >
              {credenciais.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.provedor} · vault #{c.id}
                </option>
              ))}
            </select>
          ) : (
            <span className="protocolarHint">
              <LockKeyhole size={13} /> Nenhuma credencial ativa no vault — o protocolo simulado
              segue sem assinatura. Cadastre em Configurações → Vault.
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
            Confirmar protocolo (simulado)
          </button>
        </div>
      </div>
    </div>
  );
}
