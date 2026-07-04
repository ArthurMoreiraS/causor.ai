"use client";

import { Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AuditLog, carregarAuditoria, listarUsuarios } from "@/lib/api";

type UserNameMap = Record<number, string>;

function auditActorLabel(actor: string, userNames: UserNameMap): string {
  const userMatch = /^usuario:(\d+)$/.exec(actor);
  if (!userMatch) return actor;
  const userId = Number(userMatch[1]);
  return userNames[userId] ?? `Usuário #${userId}`;
}

export default function AuditPanel({ offline }: { offline: boolean }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [userNames, setUserNames] = useState<UserNameMap>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (offline) return;
    let cancelled = false;

    async function loadAudit() {
      const [auditResult, usersResult] = await Promise.allSettled([
        carregarAuditoria(),
        listarUsuarios()
      ]);
      if (cancelled) return;

      if (auditResult.status === "fulfilled") {
        setLogs(auditResult.value);
        setError(null);
      } else {
        setError(
          auditResult.reason instanceof Error
            ? auditResult.reason.message
            : "Falha ao carregar auditoria"
        );
      }

      if (usersResult.status === "fulfilled") {
        setUserNames(
          Object.fromEntries(
            usersResult.value.map((user) => [
              user.id,
              user.nome?.trim() || user.email || `Usuário #${user.id}`
            ])
          )
        );
      }
    }

    void loadAudit();
    return () => {
      cancelled = true;
    };
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
          <article className="auditLogRow" key={log.id}>
            <strong>{log.acao}</strong>
            <span>
              {auditActorLabel(log.ator, userNames)} · {log.entidade ?? "-"}
              {log.entidade_id != null ? ` #${log.entidade_id}` : ""}
            </span>
          </article>
        ))}
        {!logs.length && !error ? <div className="empty">Sem eventos registrados</div> : null}
      </div>
    </section>
  );
}
