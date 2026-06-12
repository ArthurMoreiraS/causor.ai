"use client";

import { Bell, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AlertaPrazo, carregarAlertas } from "@/lib/api";
import { formatDate } from "@/lib/format";

const READ_KEY = "causor.radar.read.v1";

function alertKey(alerta: AlertaPrazo) {
  return `${alerta.prazo_id}:${alerta.data_fatal}`;
}

function readStored(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(READ_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function nivelLabel(nivel: AlertaPrazo["nivel"], dias: number) {
  if (nivel === "vencido") return `Vencido há ${Math.abs(dias)}d`;
  if (nivel === "d0") return "Vence hoje";
  if (nivel === "d1") return "Vence em 1 dia";
  return `Vence em ${dias} dias`;
}

export default function RadarBell({
  offline,
  refreshKey,
  onGoToPrazos
}: {
  offline: boolean;
  /** Muda quando o dashboard recarrega, para o radar acompanhar. */
  refreshKey: number;
  onGoToPrazos: () => void;
}) {
  const [alertas, setAlertas] = useState<AlertaPrazo[]>([]);
  const [read, setRead] = useState<string[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setRead(readStored());
  }, []);

  useEffect(() => {
    if (offline) return;
    let cancelled = false;
    carregarAlertas()
      .then((data) => {
        if (!cancelled) setAlertas(data);
      })
      .catch(() => {
        /* radar é melhor-esforço; o painel de prazos continua sendo a fonte */
      });
    return () => {
      cancelled = true;
    };
  }, [offline, refreshKey]);

  const unread = useMemo(
    () => alertas.filter((alerta) => !read.includes(alertKey(alerta))),
    [alertas, read]
  );

  function markAllRead() {
    const next = alertas.map(alertKey);
    setRead(next);
    try {
      window.localStorage.setItem(READ_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="radarWrap">
      <button
        className={`iconButton radarBell ${unread.length ? "hasUnread" : ""}`}
        title="Radar de Prazo"
        aria-label="Radar de Prazo"
        onClick={() => setOpen((o) => !o)}
      >
        <Bell size={15} />
        {unread.length ? <span className="radarCount mono">{unread.length}</span> : null}
      </button>

      {open ? (
        <div className="radarPanel">
          <header>
            <strong>Radar de Prazo</strong>
            <button className="iconButton" onClick={() => setOpen(false)} aria-label="Fechar">
              <X size={14} />
            </button>
          </header>
          <div className="radarBody">
            {alertas.map((alerta) => {
              const lido = read.includes(alertKey(alerta));
              return (
                <button
                  className={`radarItem ${alerta.nivel} ${lido ? "read" : ""}`}
                  key={alertKey(alerta)}
                  onClick={() => {
                    setOpen(false);
                    onGoToPrazos();
                  }}
                >
                  <div>
                    <strong>{alerta.descricao ?? "Prazo"}</strong>
                    <span className="mono">{alerta.processo_numero ?? "Processo não identificado"}</span>
                  </div>
                  <div className="radarItemMeta">
                    <span className={`dayBadge ${alerta.nivel === "vencido" || alerta.nivel === "d0" || alerta.nivel === "d1" ? "risk" : "today"}`}>
                      {nivelLabel(alerta.nivel, alerta.dias_para_vencer)}
                    </span>
                    <small>{formatDate(alerta.data_fatal)}</small>
                  </div>
                </button>
              );
            })}
            {!alertas.length ? (
              <div className="radarEmpty">Nenhum prazo em D-3, D-1 ou vencido. Bom sinal.</div>
            ) : null}
          </div>
          {alertas.length ? (
            <footer>
              <button className="toolbarButton compact" onClick={markAllRead}>
                Marcar como lidos
              </button>
            </footer>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
