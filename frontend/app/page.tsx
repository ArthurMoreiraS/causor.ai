"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  FilePenLine,
  Gavel,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  DashboardData,
  gerarMinuta,
  loadDashboard,
  Peticao,
  Prazo,
  protocolarPeticao
} from "@/lib/api";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

function daysUntil(value: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(value);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

function statusLabel(status: Peticao["status"]) {
  if (status === "rascunho") return "Aguardando revisao";
  if (status === "aprovada") return "Aprovada";
  if (status === "protocolada") return "Protocolada";
  return status;
}

export default function Home() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setData(await loadDashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados");
      setData(emptyData);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Acao nao concluida");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => {
    const openDeadlines = data.prazos.filter((p) => !p.cumprido);
    const urgent = openDeadlines.filter((p) => daysUntil(p.data_fatal) <= 3).length;
    return {
      intimacoes: data.intimacoes.length,
      prazos: openDeadlines.length,
      urgentes: urgent,
      rascunhos: data.peticoes.filter((p) => p.status === "rascunho").length
    };
  }, [data]);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">
            <Gavel size={20} />
          </div>
          <div>
            <strong>Causor</strong>
            <span>Operacao juridica</span>
          </div>
        </div>

        <nav className="nav">
          <a className="active" href="#inbox">
            <Bot size={16} /> Torre de controle
          </a>
          <a href="#prazos">
            <Clock3 size={16} /> Prazos
          </a>
          <a href="#peticoes">
            <FilePenLine size={16} /> Peticoes
          </a>
          <a href="#gate">
            <ShieldCheck size={16} /> Gate humano
          </a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">System of record + agente vertical</p>
            <h1>Operacao processual</h1>
          </div>
          <button className="iconText" onClick={refresh} disabled={loading}>
            {loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            Atualizar
          </button>
        </header>

        {error ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        <section className="metrics">
          <Metric label="Intimacoes capturadas" value={metrics.intimacoes} icon={<Bot />} />
          <Metric label="Prazos em aberto" value={metrics.prazos} icon={<Clock3 />} />
          <Metric label="Risco em 3 dias" value={metrics.urgentes} icon={<AlertTriangle />} />
          <Metric label="Minutas pendentes" value={metrics.rascunhos} icon={<FilePenLine />} />
        </section>

        <section className="grid">
          <Panel id="inbox" title="Inbox de intimacoes" action={`${data.intimacoes.length} itens`}>
            <div className="list">
              {data.intimacoes.map((item) => (
                <article className="row" key={item.id}>
                  <div>
                    <strong>{item.tipo_comunicacao ?? "Comunicacao"}</strong>
                    <span>{item.numero_processo ?? "Processo nao identificado"}</span>
                  </div>
                  <div className="rowMeta">
                    <span>{item.tribunal ?? "-"}</span>
                    <span>{formatDate(item.data_disponibilizacao)}</span>
                  </div>
                  <button
                    className="iconButton"
                    title="Gerar minuta"
                    disabled={busy === `draft-${item.id}`}
                    onClick={() =>
                      runAction(`draft-${item.id}`, () => gerarMinuta(item.id))
                    }
                  >
                    {busy === `draft-${item.id}` ? (
                      <Loader2 className="spin" size={16} />
                    ) : (
                      <Sparkles size={16} />
                    )}
                  </button>
                </article>
              ))}
              {!data.intimacoes.length ? <Empty label="Nenhuma intimacao capturada" /> : null}
            </div>
          </Panel>

          <Panel id="prazos" title="Painel de prazos" action="ordenado por vencimento">
            <div className="deadlineList">
              {data.prazos.map((prazo) => (
                <DeadlineRow key={prazo.id} prazo={prazo} />
              ))}
              {!data.prazos.length ? <Empty label="Nenhum prazo registrado" /> : null}
            </div>
          </Panel>

          <Panel id="peticoes" title="Fila de aprovacao" action={`${data.peticoes.length} minutas`}>
            <div className="petitionList">
              {data.peticoes.map((peticao) => (
                <article className="petition" key={peticao.id}>
                  <div className="petitionHead">
                    <div>
                      <strong>{peticao.tipo ?? "Peticao"}</strong>
                      <span>Processo #{peticao.processo_id}</span>
                    </div>
                    <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
                  </div>
                  <p>{peticao.conteudo ?? "Sem conteudo"}</p>
                  <div className="petitionActions">
                    <button
                      className="iconText"
                      disabled={peticao.status !== "rascunho" || busy === `approve-${peticao.id}`}
                      onClick={() =>
                        runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))
                      }
                    >
                      <CheckCircle2 size={16} />
                      Aprovar
                    </button>
                    <button
                      className="iconText dark"
                      disabled={peticao.status !== "aprovada" || busy === `file-${peticao.id}`}
                      onClick={() =>
                        runAction(`file-${peticao.id}`, () => protocolarPeticao(peticao.id))
                      }
                    >
                      <Send size={16} />
                      Protocolar
                    </button>
                  </div>
                </article>
              ))}
              {!data.peticoes.length ? <Empty label="Nenhuma minuta na fila" /> : null}
            </div>
          </Panel>

          <Panel id="gate" title="Gate humano" action="ativo">
            <div className="gate">
              <ShieldCheck size={28} />
              <div>
                <strong>Protocolo exige aprovacao</strong>
                <span>
                  Peticoes em rascunho nao podem ser marcadas como protocoladas pela API.
                </span>
              </div>
            </div>
          </Panel>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="metric">
      <div className="metricIcon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({
  id,
  title,
  action,
  children
}: {
  id: string;
  title: string;
  action: string;
  children: ReactNode;
}) {
  return (
    <section className="panel" id={id}>
      <header>
        <h2>{title}</h2>
        <span>{action}</span>
      </header>
      {children}
    </section>
  );
}

function DeadlineRow({ prazo }: { prazo: Prazo }) {
  const remaining = daysUntil(prazo.data_fatal);
  const risk = prazo.cumprido ? "done" : remaining <= 3 ? "risk" : "normal";
  return (
    <article className={`deadline ${risk}`}>
      <div>
        <strong>{prazo.descricao ?? "Prazo processual"}</strong>
        <span>{prazo.dias} dias {prazo.dias_uteis ? "uteis" : "corridos"}</span>
      </div>
      <div className="deadlineDate">
        <span>{formatDate(prazo.data_fatal)}</span>
        <small>{prazo.cumprido ? "cumprido" : `${remaining} dias`}</small>
      </div>
    </article>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="empty">
      <span>{label}</span>
    </div>
  );
}
