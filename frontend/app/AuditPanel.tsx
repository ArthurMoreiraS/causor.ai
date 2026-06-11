"use client";

import { Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AuditLog, carregarAuditoria } from "@/lib/api";

export default function AuditPanel({ offline }: { offline: boolean }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (offline) return;
    carregarAuditoria()
      .then(setLogs)
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar auditoria"));
  }, [offline]);

  return (
    <section className="panel">
      <header>
        <h2>
          <Table2 size={15} /> Auditoria
        </h2>
        <span>trilha imutável</span>
      </header>
      {error ? <div className="assistantError">{error}</div> : null}
      <div className="auditList">
        {logs.map((log) => (
          <article className="auditItem" key={log.id}>
            <div>
              <strong>{log.acao}</strong>
              <span>
                {log.ator} · {log.entidade ?? "-"}
                {log.entidade_id != null ? ` #${log.entidade_id}` : ""}
              </span>
            </div>
          </article>
        ))}
        {!logs.length && !error ? <div className="empty">Sem eventos registrados</div> : null}
      </div>
    </section>
  );
}
