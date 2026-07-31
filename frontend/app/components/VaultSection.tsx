"use client";

import { LockKeyhole } from "lucide-react";
import { useEffect, useState } from "react";
import { CredencialAssinatura, listarCredenciais } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { AsyncState, Skeleton } from "./ui";

// A sessão do tribunal deixou de viver no backend: o login roda no computador
// pareado do advogado (ver "Seu computador", acima). Aqui ficam apenas as
// referências de assinatura em nuvem (cloud_cert) — que não são sessão de
// navegação.
export default function VaultSection({ offline }: { offline: boolean }) {
  const [credenciais, setCredenciais] = useState<CredencialAssinatura[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  async function reload() {
    try {
      setCredenciais(await listarCredenciais());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Falha ao carregar as credenciais de assinatura"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (offline) {
      setLoading(false);
      return;
    }
    void reload();
  }, [offline]);

  const assinatura = credenciais.filter((c) => c.tipo !== "session");

  return (
    <div className="settingsGroup">
      <span className="settingsLabel">Assinatura em nuvem</span>
      <small className="settingsHint vaultHint">
        <LockKeyhole size={13} />
        Referências de provedores de assinatura em nuvem (BirdID, etc.). Não guardam
        senha nem certificado — apenas o apontamento do provedor. Não habilitam
        protocolo direto; o login no tribunal fica em “Seu computador”, acima.
      </small>

      <div className="vaultList">
        <AsyncState
          loading={loading}
          error={error}
          empty={!assinatura.length}
          skeleton={<Skeleton height={50} radius={8} />}
          emptyState={
            <small className="settingsHint">
              Nenhuma referência de assinatura em nuvem cadastrada.
            </small>
          }
          retrying={retrying}
          onRetry={() => {
            setRetrying(true);
            void reload().finally(() => setRetrying(false));
          }}
        >
          {assinatura.map((credencial) => (
            <article className="vaultItem" key={credencial.id}>
              <div>
                <strong>{credencial.provedor}</strong>
                <div className="pill ativa">{credencial.ativo ? "Ativa" : "Inativa"}</div>
              </div>
            </article>
          ))}
        </AsyncState>
      </div>
    </div>
  );
}
