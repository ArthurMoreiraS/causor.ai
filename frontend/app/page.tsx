"use client";

import {
  AlertTriangle,
  Bot,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  Download,
  FilePenLine,
  Gavel,
  HelpCircle,
  HomeIcon,
  Loader2,
  LockKeyhole,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  UserRound,
  Workflow
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  CaptureResult,
  cumprirPrazo,
  DashboardData,
  gerarMinuta,
  loadDashboard,
  Peticao,
  Prazo,
  ProposedAction,
  protocolarPeticao,
  ReviewQueueItem,
  rodarCapturaDemo,
  rodarCapturaOab
} from "@/lib/api";
import AssistantPanel from "./AssistantPanel";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

const API_BASE_LABEL = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const workflow = [
  { key: "capture", label: "Captura", detail: "DJEN + DataJud", status: "live" },
  { key: "deadline", label: "Prazo", detail: "Motor determinístico", status: "live" },
  { key: "draft", label: "Minuta", detail: "Claude + templates", status: "review" },
  { key: "approval", label: "Aprovação", detail: "Gate OAB", status: "review" },
  { key: "filing", label: "Protocolo", detail: "PJe / e-SAJ", status: "next" }
];

const connectors = [
  { name: "DJEN", detail: "captura oficial", status: "online" },
  { name: "DataJud", detail: "andamentos e metadados", status: "online" },
  { name: "PJe", detail: "protocolo assistido", status: "pilot" },
  { name: "e-SAJ", detail: "próximo conector", status: "planned" }
];

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
  if (status === "rascunho") return "Revisão";
  if (status === "aprovada") return "Aprovada";
  if (status === "protocolada") return "Protocolada";
  return status;
}

function connectorStatusLabel(status: string) {
  if (status === "online") return "ativo";
  if (status === "pilot") return "piloto";
  if (status === "planned") return "planejado";
  if (status === "live") return "ativo";
  if (status === "review") return "revisão";
  return status;
}

function reviewStatusLabel(status: string) {
  if (status === "capturada") return "Capturada";
  if (status === "prazo_calculado") return "Prazo calculado";
  if (status === "minuta_em_revisao") return "Minuta em revisão";
  if (status === "pronta_para_protocolo") return "Pronta para protocolo";
  if (status === "protocolada") return "Protocolada";
  if (status === "cumprido") return "Cumprido";
  return status;
}

export default function Home() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [lastClassificacao, setLastClassificacao] = useState<{
    intimacaoId: number;
    tipo: string;
    confianca: number;
  } | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [oabForm, setOabForm] = useState<{ open: boolean; oab: string; uf: string }>({
    open: false,
    oab: "",
    uf: "SP"
  });

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setData(await loadDashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar o Causor");
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
      setError(err instanceof Error ? err.message : "Ação não concluída");
    } finally {
      setBusy(null);
    }
  }

  async function runCapture() {
    setBusy("capture");
    setError(null);
    setCaptureResult(null);
    try {
      const result = await rodarCapturaDemo();
      setCaptureResult(result);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Captura não concluída");
    } finally {
      setBusy(null);
    }
  }

  async function runCaptureOab() {
    setBusy("capture");
    setError(null);
    setCaptureResult(null);
    try {
      const result = await rodarCapturaOab(oabForm.oab.trim(), oabForm.uf.trim());
      setCaptureResult(result);
      setOabForm((f) => ({ ...f, open: false }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Captura por OAB não concluída");
    } finally {
      setBusy(null);
    }
  }

  async function confirmAssistantAction(action: ProposedAction) {
    const id = Number(
      action.payload.intimacao_id ?? action.payload.prazo_id ?? action.payload.peticao_id
    );
    if (action.tipo === "gerar_minuta") await gerarMinuta(id);
    else if (action.tipo === "marcar_prazo_cumprido") await cumprirPrazo(id);
    else if (action.tipo === "aprovar_peticao") await aprovarPeticao(id);
    await refresh();
  }

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => {
    const openDeadlines = data.prazos.filter((p) => !p.cumprido);
    const highRisk = openDeadlines.filter((p) => daysUntil(p.data_fatal) <= 3).length;
    const drafts = data.peticoes.filter((p) => p.status === "rascunho").length;
    const approved = data.peticoes.filter((p) => p.status === "aprovada").length;
    return {
      monitored: data.processos.length,
      captured: data.intimacoes.length,
      pending: openDeadlines.length,
      highRisk,
      drafts,
      approved,
      hoursReturned: Math.max(8, data.intimacoes.length * 3 + data.peticoes.length * 2),
      automationRate: data.demoMode ? 92 : Math.min(99, 70 + data.intimacoes.length * 4)
    };
  }, [data]);

  const reviewQueue = useMemo<ReviewQueueItem[]>(() => {
    if (data.reviewQueue?.length) return data.reviewQueue;
    return data.intimacoes.map((intimacao) => {
      const prazo = data.prazos.find((p) => p.intimacao_id === intimacao.id) ?? null;
      const processo = data.processos.find((p) => p.id === intimacao.processo_id) ?? null;
      const peticao =
        data.peticoes.find((p) => p.prazo_id === prazo?.id) ??
        data.peticoes.find((p) => p.processo_id === processo?.id) ??
        null;
      const dias = prazo ? daysUntil(prazo.data_fatal) : null;
      return {
        intimacao,
        processo,
        prazo,
        peticao,
        status: prazo?.cumprido
          ? "cumprido"
          : peticao?.status === "aprovada"
            ? "pronta_para_protocolo"
            : peticao?.status === "rascunho"
              ? "minuta_em_revisao"
              : prazo
                ? "prazo_calculado"
                : "capturada",
        risco: prazo?.cumprido
          ? "cumprido"
          : dias === null
            ? "sem_prazo"
            : dias < 0
              ? "vencido"
              : dias <= 3
                ? "alto"
                : "baixo",
        dias_para_vencer: dias
      };
    });
  }, [data]);

  const filteredQueue = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return reviewQueue;
    return reviewQueue.filter((item) =>
      [
        item.intimacao.numero_processo,
        item.intimacao.tribunal,
        item.intimacao.tipo_comunicacao,
        item.intimacao.teor,
        item.processo?.sistema,
        item.status
      ]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(normalized))
    );
  }, [query, reviewQueue]);

  const offline = Boolean(data.backendOffline);
  const operationalWorkflow = data.operational?.workflow ?? workflow;
  const operationalConnectors = data.operational?.connectors ?? connectors;
  const operationalAudit = data.operational?.audit_signals ?? [
    {
      key: "gate",
      title: "Gate humano ativo",
      detail: "Protocolo exige aprovação do advogado."
    },
    {
      key: "secrets",
      title: "Segredos fora do prompt",
      detail: "Certificados e senhas pertencem ao vault."
    },
    {
      key: "audit",
      title: "Log operacional",
      detail: "Cada passo do agente fica rastreável."
    }
  ];

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Gavel size={18} />
          </div>
          <strong>Causor</strong>
          <span>PILOTO</span>
        </div>

        <nav className="sideNav">
          <NavItem icon={<HomeIcon size={15} />} label="Início" />
          <NavGroup label="Agentes">
            <NavItem icon={<Bot size={15} />} label="Operações Processuais" active />
            <NavItem icon={<FilePenLine size={15} />} label="Minutas" />
            <NavItem icon={<ShieldCheck size={15} />} label="Gate OAB" />
            <NavItem icon={<CalendarDays size={15} />} label="Calendário Forense" />
          </NavGroup>
          <NavGroup label="Sistema de Registro">
            <NavItem icon={<HomeIcon size={15} />} label="Processos" />
            <NavItem icon={<MessageCircle size={15} />} label="Intimações" />
            <NavItem icon={<Clock3 size={15} />} label="Prazos" />
            <NavItem icon={<Table2 size={15} />} label="Auditoria" />
          </NavGroup>
        </nav>

        <div className="sidebarFooter">
          <NavItem icon={<HelpCircle size={15} />} label="Ajuda" />
          <NavItem icon={<Settings size={15} />} label="Configurações" />
          <div className="profile">
            <div className="avatar">AM</div>
            <div>
              <strong>Arthur Moreira</strong>
              <span>causor.ai</span>
            </div>
            <ChevronDown size={14} />
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="appbar">
          <div className="crumbs">
            <span>Legal Ops</span>
            <ChevronRight size={13} />
            <strong>Agente Operacional Jurídico</strong>
          </div>
          <div className="appActions">
            <button className="toolbarButton">
              <Settings size={15} />
              Configurações
            </button>
            <button className="toolbarButton">
              <Clock3 size={15} />
              Atividade
            </button>
            <button className="toolbarButton" onClick={refresh} disabled={loading}>
              {loading ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
              Atualizar
            </button>
            <button
              className="toolbarButton"
              onClick={() => setAssistantOpen((v) => !v)}
            >
              <MessageCircle size={15} />
              Assistente
            </button>
            <button
              className="toolbarButton primary"
              onClick={runCapture}
              disabled={busy === "capture" || offline}
            >
              {busy === "capture" ? <Loader2 className="spin" size={15} /> : <Bot size={15} />}
              Rodar captura
            </button>
            <button
              className="toolbarButton"
              onClick={() => setOabForm((f) => ({ ...f, open: true }))}
              disabled={offline}
            >
              <Search size={15} />
              Captura por OAB
            </button>
          </div>
        </header>

        <section className="hero">
          <div>
            <p className="agentKicker">Plataforma de agentes Causor</p>
            <h1>Agente de Operações Processuais</h1>
          </div>
          <div className="heroSignal">
            <span>{data.demoMode ? "Demonstração para piloto" : "Ambiente ativo"}</span>
            <strong>{metrics.automationRate}%</strong>
            <small>fluxo automatizado até o gate</small>
          </div>
        </section>

        {offline ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>
              Backend offline — exibindo dados de demonstração. As ações ficam
              desativadas até o servidor da API responder em {API_BASE_LABEL}.
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        {captureResult ? (
          <div className="notice success">
            <CheckCircle2 size={18} />
            <span>
              Captura concluída: {captureResult.intimacoes_novas} intimações novas,{" "}
              {captureResult.processos_enriquecidos} processos enriquecidos e{" "}
              {captureResult.prazos_registrados} prazos registrados.
            </span>
          </div>
        ) : null}

        {lastClassificacao ? (
          <div className="notice success">
            <Sparkles size={18} />
            <span>
              Minuta classificada pela IA: <strong>{lastClassificacao.tipo}</strong> ·
              confiança {Math.round(lastClassificacao.confianca * 100)}%
            </span>
          </div>
        ) : null}

        <section className="metricStrip">
          <Metric label="Processos Monitorados" value={metrics.monitored} />
          <Metric label="Intimações Capturadas" value={metrics.captured} />
          <Metric label="Prazos Pendentes" value={metrics.pending} />
          <Metric label="Alto Risco" value={metrics.highRisk} />
        </section>

        <section className="workflowStrip" aria-label="Fluxo operacional">
          {operationalWorkflow.map((step, index) => (
            <div className={`workflowStep ${step.status}`} key={step.key}>
              <div className="stepIndex">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <strong>{step.label}</strong>
                <span>{step.detail}</span>
              </div>
            </div>
          ))}
        </section>

        <section className="statusTabs">
          <button className="statusTab active">
            <Clock3 size={15} />
            Pendentes
          </button>
          <button className="statusTab">
            <Sparkles size={15} />
            Minutadas
          </button>
          <button className="statusTab">
            <CheckCircle2 size={15} />
            Aprovadas
          </button>
          <button className="statusTab">
            <Send size={15} />
            Protocoladas
          </button>
        </section>

        <section className="workSurface">
          <div className="viewbar">
            <div className="segmented">
              <button className="selected">Operação</button>
              <button>Calendário</button>
              <button>Tabela</button>
            </div>
            <div className="viewActions">
              <label className="search">
                <Search size={15} />
                <input
                  placeholder="Buscar processo, tribunal ou ato"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <button className="toolbarButton compact">
                <SlidersHorizontal size={15} />
                Filtros
              </button>
              <button className="toolbarButton compact">
                <Download size={15} />
                Exportar
              </button>
            </div>
          </div>

          <section className="amountCards">
            <AmountCard label="Horas devolvidas" value={metrics.hoursReturned} detail="estimativa mensal" />
            <AmountCard label="Minutas em revisão" value={metrics.drafts} detail="aguardando advogado" />
            <AmountCard label="Prontas para protocolo" value={metrics.approved} detail="gate aprovado" />
          </section>

          <section className="tablePanel">
            <div className="tableHeader">
              <span>Processo</span>
              <span>Sistema</span>
              <span>Vencimento</span>
              <span>Risco</span>
              <span>Status</span>
              <span>Ações</span>
            </div>
            <div className="tableBody">
              {filteredQueue.map((item) => {
                const { intimacao, prazo, processo } = item;
                return (
                  <article className="caseRow" key={intimacao.id}>
                    <div className="caseCell">
                      <ChevronRight size={14} />
                      <div>
                        <strong>{intimacao.numero_processo ?? "Processo não identificado"}</strong>
                        <span>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</span>
                        <small>{intimacao.teor ?? "Teor não informado"}</small>
                      </div>
                    </div>
                    <span>{processo?.sistema ?? intimacao.tribunal ?? "-"}</span>
                    <strong>
                      {prazo ? formatDate(prazo.data_fatal) : formatDate(intimacao.data_publicacao)}
                    </strong>
                    <DeadlineBadge prazo={prazo} />
                    <span className={`queueStatus ${item.status}`}>
                      {reviewStatusLabel(item.status)}
                    </span>
                    <div className="rowActions">
                      <button
                        className="iconButton"
                        title="Gerar minuta"
                        disabled={busy === `draft-${intimacao.id}` || offline}
                        onClick={() =>
                          runAction(`draft-${intimacao.id}`, async () => {
                            const cls = await gerarMinuta(intimacao.id);
                            if (cls)
                              setLastClassificacao({
                                intimacaoId: intimacao.id,
                                tipo: cls.tipo,
                                confianca: cls.confianca
                              });
                          })
                        }
                      >
                        {busy === `draft-${intimacao.id}` ? (
                          <Loader2 className="spin" size={15} />
                        ) : (
                          <Sparkles size={15} />
                        )}
                      </button>
                      <button
                        className="iconButton"
                        title="Marcar prazo cumprido"
                        disabled={!prazo || prazo.cumprido || busy === `done-${prazo?.id}` || offline}
                        onClick={() =>
                          prazo
                            ? runAction(`done-${prazo.id}`, () => cumprirPrazo(prazo.id))
                            : undefined
                        }
                      >
                        {busy === `done-${prazo?.id}` ? (
                          <Loader2 className="spin" size={15} />
                        ) : (
                          <CheckCircle2 size={15} />
                        )}
                      </button>
                    </div>
                  </article>
                );
              })}
              {!filteredQueue.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
            </div>
          </section>
        </section>

        <section className="insightGrid">
          <Panel title="Conectores" action="oficiais primeiro">
            <div className="connectorGrid">
              {operationalConnectors.map((connector) => (
                <article className={`connector ${connector.status}`} key={connector.name}>
                  <div>
                    <strong>{connector.name}</strong>
                    <span>{connector.detail}</span>
                  </div>
                  <small>{connectorStatusLabel(connector.status)}</small>
                </article>
              ))}
            </div>
          </Panel>

          <Panel title="Tese do produto" action="moat">
            <div className="thesis">
              <Workflow size={24} />
              <div>
                <strong>Da intimação ao protocolo</strong>
                <span>
                  O Causor centraliza o SOR, calcula prazos sem LLM, minuta com Claude e
                  preserva o gate humano antes de qualquer ato irreversível.
                </span>
              </div>
            </div>
          </Panel>
        </section>

        <section className="bottomGrid">
          <Panel title="Fila de aprovação" action={`${data.peticoes.length} minutas`}>
            <div className="petitionList">
              {data.peticoes.map((peticao) => (
                <article className="petition" key={peticao.id}>
                  <div className="petitionHead">
                    <div>
                      <strong>{peticao.tipo ?? "Petição"}</strong>
                      <span>Processo #{peticao.processo_id}</span>
                    </div>
                    <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
                  </div>
                  <p>{peticao.conteudo ?? "Sem conteúdo"}</p>
                  <div className="petitionActions">
                    <button
                      className="toolbarButton"
                      disabled={peticao.status !== "rascunho" || busy === `approve-${peticao.id}` || offline}
                      onClick={() =>
                        runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))
                      }
                    >
                      <CheckCircle2 size={15} />
                      Aprovar
                    </button>
                    <button
                      className="toolbarButton primary"
                      disabled={peticao.status !== "aprovada" || busy === `file-${peticao.id}` || offline}
                      onClick={() =>
                        runAction(`file-${peticao.id}`, () => protocolarPeticao(peticao.id))
                      }
                    >
                      <Send size={15} />
                      Protocolar
                    </button>
                  </div>
                </article>
              ))}
              {!data.peticoes.length ? <Empty label="Nenhuma minuta aguardando aprovação" /> : null}
            </div>
          </Panel>

          <Panel title="Auditoria e segurança" action="imutável">
            <div className="auditList">
              {operationalAudit.map((item, index) => (
                <AuditItem
                  key={item.key}
                  icon={
                    index === 0 ? (
                      <ShieldCheck size={15} />
                    ) : index === 1 ? (
                      <LockKeyhole size={15} />
                    ) : (
                      <CircleDot size={15} />
                    )
                  }
                  title={item.title}
                  detail={item.detail}
                />
              ))}
            </div>
          </Panel>
        </section>

        {oabForm.open ? (
          <div className="modalOverlay" onClick={() => setOabForm((f) => ({ ...f, open: false }))}>
            <div className="modalCard" onClick={(e) => e.stopPropagation()}>
              <h3>Captura por OAB</h3>
              <label>
                OAB
                <input
                  value={oabForm.oab}
                  onChange={(e) => setOabForm((f) => ({ ...f, oab: e.target.value }))}
                  placeholder="123456"
                />
              </label>
              <label>
                UF
                <input
                  value={oabForm.uf}
                  maxLength={2}
                  onChange={(e) => setOabForm((f) => ({ ...f, uf: e.target.value.toUpperCase() }))}
                />
              </label>
              <div className="modalActions">
                <button className="toolbarButton" onClick={() => setOabForm((f) => ({ ...f, open: false }))}>
                  Cancelar
                </button>
                <button
                  className="toolbarButton primary"
                  disabled={!oabForm.oab.trim() || busy === "capture"}
                  onClick={() => void runCaptureOab()}
                >
                  {busy === "capture" ? <Loader2 className="spin" size={15} /> : null}
                  Capturar
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>
      {assistantOpen ? (
        <AssistantPanel
          offline={offline}
          onConfirmAction={confirmAssistantAction}
          onClose={() => setAssistantOpen(false)}
        />
      ) : null}
    </main>
  );
}

function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="navGroup">
      <div className="navGroupLabel">
        <span>{label}</span>
        <ChevronDown size={12} />
      </div>
      {children}
    </div>
  );
}

function NavItem({
  icon,
  label,
  active = false
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <a className={active ? "active" : ""} href="#">
      {icon}
      <span>{label}</span>
    </a>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AmountCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <article className="amountCard">
      <span>{label}</span>
      <strong>{value.toLocaleString("pt-BR")}</strong>
      <small>{detail}</small>
    </article>
  );
}

function Panel({
  title,
  action,
  children
}: {
  title: string;
  action: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header>
        <h2>{title}</h2>
        <span>{action}</span>
      </header>
      {children}
    </section>
  );
}

function DeadlineBadge({ prazo }: { prazo: Prazo | null | undefined }) {
  if (!prazo) return <span className="dayBadge neutral">Pendente</span>;
  const remaining = daysUntil(prazo.data_fatal);
  if (prazo.cumprido) return <span className="dayBadge done">Concluído</span>;
  if (remaining <= 0) return <span className="dayBadge risk">Vencido</span>;
  if (remaining <= 3) return <span className="dayBadge today">{remaining}d</span>;
  return <span className="dayBadge neutral">{remaining}d</span>;
}

function AuditItem({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <article className="auditItem">
      <div className="auditIcon">{icon}</div>
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </article>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="empty">
      <UserRound size={18} />
      <span>{label}</span>
    </div>
  );
}
