"use client";

import {
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  CircleDot,
  Clock3,
  Download,
  FilePenLine,
  HelpCircle,
  HomeIcon,
  Loader2,
  LockKeyhole,
  MessageCircle,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Workflow,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  CaptureResult,
  cumprirPrazo,
  DashboardData,
  editarPeticao,
  gerarMinuta,
  loadDashboard,
  Peticao,
  Prazo,
  ProposedAction,
  protocolarPeticaoAsync,
  revisarPrazo,
  ReviewQueueItem,
  rodarCapturaOab
} from "@/lib/api";
import AuditPanel from "./AuditPanel";
import SettingsModal from "./SettingsModal";
import DetailDrawer, { DetailSelection } from "./DetailDrawer";
import MinutaEditor from "./MinutaEditor";
import PrazoEditModal, { PrazoPatch } from "./PrazoEditModal";
import FiltersPanel from "./components/FiltersPanel";
import HelpModal from "./components/HelpModal";
import ProfileModal from "./components/ProfileModal";
import ProtocolarModal from "./components/ProtocolarModal";
import QueueTable from "./components/QueueTable";
import RadarBell from "./components/RadarBell";
import {
  AmountCard,
  AuditItem,
  Empty,
  Metric,
  NavGroup,
  NavItem,
  Panel
} from "./components/ui";
import AssistantWorkspace from "./views/AssistantWorkspace";
import ConectoresView from "./views/ConectoresView";
import FilaDoDiaView from "./views/FilaDoDiaView";
import GateOabView from "./views/GateOabView";
import HomeDashboard from "./views/HomeDashboard";
import ProtocolosView from "./views/ProtocolosView";
import TemplatesView from "./views/TemplatesView";
import IntimacoesView from "./views/IntimacoesView";
import PeticoesView from "./views/PeticoesView";
import PrazosView from "./views/PrazosView";
import ProcessosView from "./views/ProcessosView";
import { useRequireAuth } from "./AuthProvider";
import { useSettings } from "@/lib/settings";
import { downloadCsv } from "@/lib/export";
import {
  connectorStatusLabel,
  daysUntil,
  matchesQuery,
  passesFilters,
  reviewStatusLabel,
  riscoFromDias,
  riskLabel,
  statusLabel
} from "@/lib/format";
import {
  CONNECTORS_FALLBACK,
  EMPTY_BY_VIEW,
  STATUS_MATCH,
  StatusKey,
  VIEW_COPY,
  VIEW_LABEL,
  ViewKey,
  WORKFLOW_FALLBACK
} from "@/lib/views";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

const API_BASE_LABEL = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Home() {
  const { loading: authLoading, session, signOut } = useRequireAuth();
  const [data, setData] = useState<DashboardData>(emptyData);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewKey>("fila");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusKey>("pendentes");
  const [error, setError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [lastClassificacao, setLastClassificacao] = useState<{
    intimacaoId: number;
    tipo: string;
    confianca: number;
  } | null>(null);
  const [lastProtocolo, setLastProtocolo] = useState<{
    tipo: string | null;
    protocolo: string;
  } | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [oabForm, setOabForm] = useState<{ open: boolean; oab: string; uf: string }>({
    open: false,
    oab: "",
    uf: "SP"
  });
  const { settings, update: updateSettings, reset: resetSettings } = useSettings();
  const [overlay, setOverlay] = useState<null | "settings" | "help" | "profile">(null);
  const [detail, setDetail] = useState<DetailSelection | null>(null);
  const [editorPeticao, setEditorPeticao] = useState<Peticao | null>(null);
  const [protocolarTarget, setProtocolarTarget] = useState<Peticao | null>(null);
  const [prazoEdit, setPrazoEdit] = useState<Prazo | null>(null);
  const [filters, setFilters] = useState<{ tribunal: string; sistema: string; risco: string }>({
    tribunal: "",
    sistema: "",
    risco: ""
  });
  const [showFilters, setShowFilters] = useState(false);

  const filtersActive = Boolean(filters.tribunal || filters.sistema || filters.risco);

  const calendarYears = useMemo(() => {
    const y = new Date().getFullYear();
    const n = settings.calendarYears;
    const start = y - Math.floor((n - 1) / 2);
    return Array.from({ length: n }, (_, i) => start + i);
  }, [settings.calendarYears]);

  function openOab() {
    setOabForm((f) => ({
      ...f,
      open: true,
      oab: f.oab || settings.defaultOab,
      uf: f.uf || settings.defaultUf
    }));
  }

  async function refresh() {
    setError(null);
    try {
      setData(await loadDashboard());
      setRefreshTick((tick) => tick + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar o Causor");
      setData(emptyData);
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
    const { payload } = action;
    if (action.tipo === "gerar_minuta")
      await gerarMinuta(Number(payload.intimacao_id), calendarYears);
    else if (action.tipo === "marcar_prazo_cumprido") await cumprirPrazo(Number(payload.prazo_id));
    else if (action.tipo === "aprovar_peticao") await aprovarPeticao(Number(payload.peticao_id));
    else throw new Error(`Ação desconhecida: ${action.tipo}`);
    await refresh();
  }

  function editarPrazo(prazo: Prazo) {
    setPrazoEdit(prazo);
  }

  function protocolar(peticao: Peticao) {
    setProtocolarTarget(peticao);
  }

  async function confirmarProtocolo(credencialId: number | null) {
    const peticao = protocolarTarget;
    if (!peticao) return;
    await runAction(`file-${peticao.id}`, async () => {
      const job = await protocolarPeticaoAsync(peticao.id, credencialId ?? undefined);
      const protocolo = job.resultado?.protocolo;
      const checkpoint = job.resultado?.checkpoint;
      setLastProtocolo({
        tipo: peticao.tipo,
        protocolo: protocolo
          ? String(protocolo)
          : checkpoint
            ? `${String(checkpoint)} · job #${job.id}`
            : `job #${job.id}`
      });
    });
    setProtocolarTarget(null);
  }

  async function salvarRevisaoPrazo(patch: PrazoPatch) {
    if (!prazoEdit) return;
    const id = prazoEdit.id;
    if (Object.keys(patch).length === 0) {
      setPrazoEdit(null);
      return;
    }
    await runAction(`edit-${id}`, async () => {
      await revisarPrazo(id, patch);
    });
    setPrazoEdit(null);
  }

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => {
    const openDeadlines = data.prazos.filter((p) => !p.cumprido);
    const highRisk = openDeadlines.filter((p) => daysUntil(p.data_fatal) <= 3).length;
    const overdue = openDeadlines.filter((p) => daysUntil(p.data_fatal) < 0).length;
    const drafts = data.peticoes.filter((p) => p.status === "rascunho").length;
    const approved = data.peticoes.filter((p) => p.status === "aprovada").length;
    const handledProcessos = new Set(data.peticoes.map((p) => p.processo_id));
    const withoutDraft = data.intimacoes.filter(
      (i) => !i.processo_id || !handledProcessos.has(i.processo_id)
    ).length;
    // Real compliance: share of pending deadlines that are not overdue.
    const compliance = openDeadlines.length
      ? Math.round(((openDeadlines.length - overdue) / openDeadlines.length) * 100)
      : 100;
    return {
      monitored: data.processos.length,
      captured: data.intimacoes.length,
      pending: openDeadlines.length,
      highRisk,
      overdue,
      drafts,
      approved,
      withoutDraft,
      compliance
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
          : peticao?.status === "protocolada"
            ? "protocolada"
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

  const scopedQueue = useMemo(() => {
    return reviewQueue.filter((item) => {
      if (view === "auditoria") return false;
      if (view === "inicio") return true;
      if (view === "prazos") return Boolean(item.prazo);
      if (view === "peticoes" || view === "gate") return Boolean(item.peticao);
      return true;
    });
  }, [reviewQueue, view]);

  const filteredQueue = useMemo(() => {
    const byStatus = scopedQueue
      .filter((item) => STATUS_MATCH[statusFilter](item.status))
      .filter((item) => passesFilters(filters, {
        tribunal: item.intimacao.tribunal ?? item.processo?.tribunal,
        sistema: item.processo?.sistema,
        risco: item.risco
      }));
    const normalized = query.trim().toLowerCase();
    if (!normalized) return byStatus;
    return byStatus.filter((item) =>
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
  }, [query, scopedQueue, statusFilter, filters]);

  const filterOptions = useMemo(() => {
    const tribunais = new Set<string>();
    const sistemas = new Set<string>();
    data.intimacoes.forEach((i) => i.tribunal && tribunais.add(i.tribunal));
    data.processos.forEach((p) => {
      if (p.tribunal) tribunais.add(p.tribunal);
      if (p.sistema) sistemas.add(p.sistema);
    });
    return {
      tribunais: Array.from(tribunais).sort(),
      sistemas: Array.from(sistemas).sort()
    };
  }, [data]);

  const statusCounts = useMemo<Record<StatusKey, number>>(
    () => ({
      pendentes: scopedQueue.filter((item) => STATUS_MATCH.pendentes(item.status)).length,
      minutadas: scopedQueue.filter((item) => STATUS_MATCH.minutadas(item.status)).length,
      aprovadas: scopedQueue.filter((item) => STATUS_MATCH.aprovadas(item.status)).length,
      protocoladas: scopedQueue.filter((item) => STATUS_MATCH.protocoladas(item.status)).length
    }),
    [scopedQueue]
  );

  const processoRows = useMemo(() => {
    return data.processos
      .map((processo) => {
        const prazos = data.prazos.filter((prazo) => prazo.processo_id === processo.id);
        const intimacoes = data.intimacoes.filter(
          (intimacao) => intimacao.processo_id === processo.id
        );
        const peticoes = data.peticoes.filter((peticao) => peticao.processo_id === processo.id);
        const proximoPrazo =
          prazos
            .filter((prazo) => !prazo.cumprido)
            .sort(
              (a, b) =>
                new Date(a.data_fatal).getTime() - new Date(b.data_fatal).getTime()
            )[0] ?? null;
        return { processo, prazos, intimacoes, peticoes, proximoPrazo };
      })
      .filter(({ processo, proximoPrazo }) =>
        passesFilters(filters, {
          tribunal: processo.tribunal,
          sistema: processo.sistema,
          risco: proximoPrazo
            ? riscoFromDias(daysUntil(proximoPrazo.data_fatal), proximoPrazo.cumprido)
            : "sem_prazo"
        })
      )
      .filter(({ processo, intimacoes, peticoes, proximoPrazo }) =>
        matchesQuery(
          [
            processo.numero,
            processo.classe,
            processo.tribunal,
            processo.orgao_julgador,
            processo.sistema,
            proximoPrazo?.descricao,
            intimacoes[0]?.tipo_comunicacao,
            peticoes[0]?.tipo
          ],
          query
        )
      );
  }, [data, query, filters]);

  const intimacaoRows = useMemo(() => {
    return data.intimacoes
      .map((intimacao) => {
        const processo = data.processos.find((item) => item.id === intimacao.processo_id) ?? null;
        const prazo = data.prazos.find((item) => item.intimacao_id === intimacao.id) ?? null;
        const peticao =
          data.peticoes.find((item) => item.prazo_id === prazo?.id) ??
          data.peticoes.find((item) => item.processo_id === processo?.id) ??
          null;
        return { intimacao, processo, prazo, peticao };
      })
      .filter(({ intimacao, processo, prazo }) =>
        passesFilters(filters, {
          tribunal: intimacao.tribunal ?? processo?.tribunal,
          sistema: processo?.sistema,
          risco: prazo ? riscoFromDias(daysUntil(prazo.data_fatal), prazo.cumprido) : "sem_prazo"
        })
      )
      .filter(({ intimacao, processo, prazo, peticao }) =>
        matchesQuery(
          [
            intimacao.numero_processo,
            intimacao.tribunal,
            intimacao.tipo_comunicacao,
            intimacao.teor,
            processo?.sistema,
            prazo?.descricao,
            peticao?.tipo
          ],
          query
        )
      );
  }, [data, query, filters]);

  const prazoRows = useMemo(() => {
    return data.prazos
      .map((prazo) => {
        const processo = data.processos.find((item) => item.id === prazo.processo_id) ?? null;
        const intimacao = data.intimacoes.find((item) => item.id === prazo.intimacao_id) ?? null;
        const peticao = data.peticoes.find((item) => item.prazo_id === prazo.id) ?? null;
        const dias = daysUntil(prazo.data_fatal);
        return { prazo, processo, intimacao, peticao, dias };
      })
      .sort((a, b) => new Date(a.prazo.data_fatal).getTime() - new Date(b.prazo.data_fatal).getTime())
      .filter(({ prazo, processo, dias }) =>
        passesFilters(filters, {
          tribunal: processo?.tribunal,
          sistema: processo?.sistema,
          risco: riscoFromDias(dias, prazo.cumprido)
        })
      )
      .filter(({ prazo, processo, intimacao, peticao }) =>
        matchesQuery(
          [
            prazo.descricao,
            prazo.data_fatal,
            processo?.numero,
            processo?.tribunal,
            intimacao?.tipo_comunicacao,
            peticao?.tipo
          ],
          query
        )
      );
  }, [data, query, filters]);

  const peticaoRows = useMemo(() => {
    return data.peticoes
      .map((peticao) => {
        const processo = data.processos.find((item) => item.id === peticao.processo_id) ?? null;
        const prazo = data.prazos.find((item) => item.id === peticao.prazo_id) ?? null;
        return { peticao, processo, prazo };
      })
      .filter(({ peticao, processo, prazo }) =>
        matchesQuery(
          [
            peticao.tipo,
            peticao.conteudo,
            peticao.status,
            processo?.numero,
            processo?.tribunal,
            prazo?.descricao
          ],
          query
        )
      );
  }, [data, query]);

  const viewCount =
    view === "processos"
      ? processoRows.length
      : view === "intimacoes"
        ? intimacaoRows.length
      : view === "prazos"
        ? prazoRows.length
        : view === "peticoes" || view === "gate"
          ? peticaoRows.length
          : filteredQueue.length;

  function exportCurrentView() {
    const stamp = new Date().toISOString().slice(0, 10);
    if (view === "processos") {
      downloadCsv(
        `causor-processos-${stamp}.csv`,
        ["Número", "Classe", "Tribunal", "Sistema", "Próximo prazo", "Intimações", "Minutas"],
        processoRows.map((r) => [
          r.processo.numero,
          r.processo.classe,
          r.processo.tribunal,
          r.processo.sistema,
          r.proximoPrazo?.data_fatal ?? "",
          r.intimacoes.length,
          r.peticoes.length
        ])
      );
    } else if (view === "intimacoes") {
      downloadCsv(
        `causor-intimacoes-${stamp}.csv`,
        ["Processo", "Tribunal", "Tipo", "Publicação", "Teor"],
        intimacaoRows.map((r) => [
          r.intimacao.numero_processo,
          r.intimacao.tribunal,
          r.intimacao.tipo_comunicacao,
          r.intimacao.data_publicacao ?? r.intimacao.data_disponibilizacao,
          r.intimacao.teor
        ])
      );
    } else if (view === "peticoes" || view === "gate") {
      downloadCsv(
        `causor-minutas-${stamp}.csv`,
        ["Tipo", "Processo", "Status", "Prazo"],
        peticaoRows.map((r) => [
          r.peticao.tipo,
          r.processo?.numero ?? r.peticao.processo_id,
          r.peticao.status,
          r.prazo?.data_fatal ?? ""
        ])
      );
    } else if (view === "prazos") {
      downloadCsv(
        `causor-prazos-${stamp}.csv`,
        ["Descrição", "Processo", "Data fatal", "Dias", "Dias úteis", "Cumprido", "Dias restantes"],
        prazoRows.map((r) => [
          r.prazo.descricao,
          r.processo?.numero ?? r.prazo.processo_id,
          r.prazo.data_fatal,
          r.prazo.dias,
          r.prazo.dias_uteis ? "sim" : "não",
          r.prazo.cumprido ? "sim" : "não",
          r.dias
        ])
      );
    } else {
      downloadCsv(
        `causor-fila-${stamp}.csv`,
        ["Processo", "Sistema", "Vencimento", "Risco", "Status"],
        filteredQueue.map((item) => [
          item.intimacao.numero_processo,
          item.processo?.sistema ?? item.intimacao.tribunal,
          item.prazo?.data_fatal ?? "",
          riskLabel(item.risco),
          reviewStatusLabel(item.status)
        ])
      );
    }
  }

  const offline = Boolean(data.backendOffline);
  const operationalWorkflow = data.operational?.workflow ?? WORKFLOW_FALLBACK;
  const operationalConnectors = data.operational?.connectors ?? CONNECTORS_FALLBACK;
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

  if (authLoading || !session) {
    return (
      <div className="authShell">
        <p className="authSub">Carregando…</p>
      </div>
    );
  }

  return (
    <main className={`shell${sidebarCollapsed ? " sidebarCollapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brandWordmark" aria-label="Causor" title="Causor">
            <img className="brandWordmarkDark" src="/brand/causor-wordmark-dark-cropped.png" alt="" />
            <img className="brandWordmarkLight" src="/brand/causor-wordmark-light-cropped.png" alt="" />
          </span>
          <button
            className="sidebarToggle"
            type="button"
            aria-label={sidebarCollapsed ? "Expandir menu lateral" : "Minimizar menu lateral"}
            title={sidebarCollapsed ? "Expandir menu" : "Minimizar menu"}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            {sidebarCollapsed ? <ChevronsRight size={15} /> : <ChevronsLeft size={15} />}
          </button>
        </div>

        <nav className="sideNav">
          <NavItem
            icon={<Zap size={15} />}
            label="Fila do dia"
            active={view === "fila"}
            onClick={() => setView("fila")}
          />
          <NavGroup label="Operação diária">
            <NavItem
              icon={<HomeIcon size={15} />}
              label="Central de Comando"
              active={view === "inicio"}
              onClick={() => setView("inicio")}
            />
            <NavItem
              icon={<MessageCircle size={15} />}
              label="Assistente"
              active={view === "assistente"}
              onClick={() => setView("assistente")}
            />
            <NavItem
              icon={<Bot size={15} />}
              label="Operações Processuais"
              active={view === "operacao"}
              onClick={() => setView("operacao")}
            />
          </NavGroup>
          <NavGroup label="Automações">
            <NavItem
              icon={<FilePenLine size={15} />}
              label="Minutas"
              active={view === "peticoes"}
              onClick={() => setView("peticoes")}
            />
            <NavItem
              icon={<BookOpen size={15} />}
              label="Templates"
              active={view === "templates"}
              onClick={() => setView("templates")}
            />
            <NavItem
              icon={<ShieldCheck size={15} />}
              label="Gate OAB"
              active={view === "gate"}
              onClick={() => setView("gate")}
            />
            <NavItem
              icon={<Send size={15} />}
              label="Protocolos"
              active={view === "protocolos"}
              onClick={() => setView("protocolos")}
            />
          </NavGroup>
          <NavGroup label="Registro">
            <NavItem
              icon={<HomeIcon size={15} />}
              label="Processos"
              active={view === "processos"}
              onClick={() => setView("processos")}
            />
            <NavItem
              icon={<MessageCircle size={15} />}
              label="Intimações"
              active={view === "intimacoes"}
              onClick={() => setView("intimacoes")}
            />
            <NavItem
              icon={<Clock3 size={15} />}
              label="Prazos"
              active={view === "prazos"}
              onClick={() => setView("prazos")}
            />
          </NavGroup>
          <NavGroup label="Governança">
            <NavItem
              icon={<Workflow size={15} />}
              label="Conectores"
              active={view === "conectores"}
              onClick={() => setView("conectores")}
            />
            <NavItem
              icon={<Table2 size={15} />}
              label="Auditoria"
              active={view === "auditoria"}
              onClick={() => setView("auditoria")}
            />
          </NavGroup>
        </nav>

        <div className="sidebarFooter">
          <NavItem
            icon={<HelpCircle size={15} />}
            label="Ajuda"
            onClick={() => setOverlay("help")}
          />
          <NavItem
            icon={<Settings size={15} />}
            label="Configurações"
            onClick={() => setOverlay("settings")}
          />
          <button className="profile" onClick={() => setOverlay("profile")}>
            <div className="avatar">AM</div>
            <div>
              <strong>Conta</strong>
              <span>Usuário do piloto</span>
            </div>
            <ChevronDown size={14} />
          </button>
        </div>
      </aside>

      <section className="workspace">
        <header className="appbar">
          <div className="crumbs">
            <span>Legal Ops</span>
            <ChevronRight size={13} />
            <strong>{VIEW_LABEL[view]}</strong>
          </div>
          <div className="appActions">
            <RadarBell
              offline={offline}
              refreshKey={refreshTick}
              onGoToPrazos={() => setView("prazos")}
            />
            <button className="toolbarButton" onClick={openOab} disabled={offline}>
              <Search size={15} />
              Captura por OAB
            </button>
          </div>
        </header>

        {view !== "assistente" && (
          <section className="hero">
            <div>
              <p className="agentKicker">Plataforma de agentes Causor</p>
              <h1>{VIEW_LABEL[view]}</h1>
              <span className="heroCopy">{VIEW_COPY[view]}</span>
            </div>
            <div className="heroSignal">
              <span>{offline ? "API indisponível" : "Prazos em dia"}</span>
              <strong>{metrics.compliance}%</strong>
              <small>{metrics.overdue} vencido(s) · {metrics.pending} pendente(s)</small>
            </div>
          </section>
        )}

        {offline ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>
              Backend offline — exibindo apenas dados persistidos já carregados. As ações ficam
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

        {lastProtocolo ? (
          <div className="notice success">
            <CheckCircle2 size={18} />
            <span>
              Fluxo de protocolo atualizado: {lastProtocolo.tipo ?? "petição"} — referência{" "}
              <strong className="mono">{lastProtocolo.protocolo}</strong>. Registrado na auditoria.
            </span>
          </div>
        ) : null}

        {lastClassificacao ? (
          <div
            className={
              lastClassificacao.confianca < settings.confidenceThreshold
                ? "notice"
                : "notice success"
            }
          >
            {lastClassificacao.confianca < settings.confidenceThreshold ? (
              <AlertTriangle size={18} />
            ) : (
              <Sparkles size={18} />
            )}
            <span>
              Minuta classificada pela IA: <strong>{lastClassificacao.tipo}</strong> · confiança{" "}
              {Math.round(lastClassificacao.confianca * 100)}%
              {lastClassificacao.confianca < settings.confidenceThreshold
                ? ` — abaixo do limiar (${Math.round(
                    settings.confidenceThreshold * 100
                  )}%), revise com atenção.`
                : ""}
            </span>
          </div>
        ) : null}

        {view === "assistente" ? (
          <AssistantWorkspace
            offline={offline}
            onConfirmAction={confirmAssistantAction}
          />
        ) : view === "fila" ? (
          <FilaDoDiaView
            items={reviewQueue}
            busy={busy}
            offline={offline}
            onGenerateDraft={(intimacaoId) =>
              runAction(`draft-${intimacaoId}`, async () => {
                const cls = await gerarMinuta(intimacaoId, calendarYears);
                if (cls)
                  setLastClassificacao({ intimacaoId, tipo: cls.tipo, confianca: cls.confianca });
              })
            }
            onOpenEditor={(peticao) => setEditorPeticao(peticao)}
            onApprove={(peticao) => runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))}
            onFile={protocolar}
            onNavigate={setView}
          />
        ) : view === "templates" ? (
          <TemplatesView offline={offline} />
        ) : view === "protocolos" ? (
          <ProtocolosView
            peticoes={data.peticoes}
            processos={data.processos}
            offline={offline}
            refreshKey={refreshTick}
          />
        ) : view === "conectores" ? (
          <ConectoresView
            connectors={operationalConnectors}
            onOpenVault={() => setOverlay("settings")}
          />
        ) : view === "inicio" ? (
          <HomeDashboard
            metrics={metrics}
            priorityQueue={reviewQueue.slice(0, 5)}
            prazoRows={prazoRows.slice(0, 5)}
            operationalConnectors={operationalConnectors}
            offline={offline}
            busy={busy}
            onOpenOab={openOab}
            onOpenAssistant={() => setView("assistente")}
            onNavigate={setView}
          />
        ) : (
        <>
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

        {view === "operacao" ? (
        <section className="statusTabs">
          <button
            className={`statusTab ${statusFilter === "pendentes" ? "active" : ""}`}
            onClick={() => setStatusFilter("pendentes")}
          >
            <Clock3 size={15} />
            Pendentes ({statusCounts.pendentes})
          </button>
          <button
            className={`statusTab ${statusFilter === "minutadas" ? "active" : ""}`}
            onClick={() => setStatusFilter("minutadas")}
          >
            <Sparkles size={15} />
            Minutadas ({statusCounts.minutadas})
          </button>
          <button
            className={`statusTab ${statusFilter === "aprovadas" ? "active" : ""}`}
            onClick={() => setStatusFilter("aprovadas")}
          >
            <CheckCircle2 size={15} />
            Aprovadas ({statusCounts.aprovadas})
          </button>
          <button
            className={`statusTab ${statusFilter === "protocoladas" ? "active" : ""}`}
            onClick={() => setStatusFilter("protocoladas")}
          >
            <Send size={15} />
            Protocoladas ({statusCounts.protocoladas})
          </button>
        </section>
        ) : null}

        {view === "auditoria" ? (
          <section className="workSurface auditSurface">
            <AuditPanel offline={offline} />
          </section>
        ) : (
        <section className="workSurface">
          <div className="viewbar">
            <div className="viewTitleBlock">
              <span className="sectionKicker">{VIEW_LABEL[view]}</span>
              <strong>{viewCount.toLocaleString("pt-BR")} registros</strong>
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
              <div className="filterWrap">
                <button
                  className={`toolbarButton compact ${filtersActive ? "accentOn" : ""}`}
                  onClick={() => setShowFilters((s) => !s)}
                >
                  <SlidersHorizontal size={15} />
                  Filtros{filtersActive ? " •" : ""}
                </button>
                {showFilters ? (
                  <FiltersPanel
                    filters={filters}
                    options={filterOptions}
                    onChange={setFilters}
                    onClear={() => setFilters({ tribunal: "", sistema: "", risco: "" })}
                    onClose={() => setShowFilters(false)}
                  />
                ) : null}
              </div>
              <button className="toolbarButton compact" onClick={exportCurrentView}>
                <Download size={15} />
                Exportar
              </button>
            </div>
          </div>

          {view === "operacao" ? (
            <>
              <section className="amountCards">
                <AmountCard label="Intimações sem minuta" value={metrics.withoutDraft} detail="aguardando redação" />
                <AmountCard label="Minutas em revisão" value={metrics.drafts} detail="aguardando advogado" />
                <AmountCard label="Prontas para protocolo" value={metrics.approved} detail="gate aprovado" />
              </section>
              <QueueTable
                items={filteredQueue}
                busy={busy}
                offline={offline}
                emptyLabel={EMPTY_BY_VIEW[view]}
                onGenerateDraft={(intimacaoId) =>
                  runAction(`draft-${intimacaoId}`, async () => {
                    const cls = await gerarMinuta(intimacaoId, calendarYears);
                    if (cls)
                      setLastClassificacao({
                        intimacaoId,
                        tipo: cls.tipo,
                        confianca: cls.confianca
                      });
                  })
                }
                onDonePrazo={(prazo) => runAction(`done-${prazo.id}`, () => cumprirPrazo(prazo.id))}
                onEditPrazo={editarPrazo}
              />
            </>
          ) : null}

          {view === "processos" ? (
            <ProcessosView
              rows={processoRows}
              onOpen={(id) => setDetail({ kind: "processo", id })}
            />
          ) : null}
          {view === "intimacoes" ? (
            <IntimacoesView
              rows={intimacaoRows}
              busy={busy}
              offline={offline}
              onOpen={(id) => setDetail({ kind: "intimacao", id })}
              onGenerateDraft={(intimacaoId) =>
                runAction(`draft-${intimacaoId}`, async () => {
                  const cls = await gerarMinuta(intimacaoId, calendarYears);
                  if (cls)
                    setLastClassificacao({
                      intimacaoId,
                      tipo: cls.tipo,
                      confianca: cls.confianca
                    });
                })
              }
            />
          ) : null}
          {view === "prazos" ? (
            <PrazosView
              rows={prazoRows}
              busy={busy}
              offline={offline}
              onOpen={(sel) => setDetail(sel)}
              onDonePrazo={(prazo) => runAction(`done-${prazo.id}`, () => cumprirPrazo(prazo.id))}
              onEditPrazo={editarPrazo}
            />
          ) : null}
          {view === "peticoes" ? (
            <PeticoesView
              rows={peticaoRows}
              onOpenEditor={(peticao) => setEditorPeticao(peticao)}
              onGoToGate={() => setView("gate")}
            />
          ) : null}
          {view === "gate" ? (
            <GateOabView
              rows={peticaoRows}
              busy={busy}
              offline={offline}
              onApprove={(peticao) => runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))}
              onFile={protocolar}
            />
          ) : null}
        </section>
        )}

        {view === "operacao" ? (
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
        ) : null}

        {view === "operacao" ? (
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
                      onClick={() => protocolar(peticao)}
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
          <AuditPanel offline={offline} />
        </section>
        ) : null}
        </>
        )}

        {oabForm.open ? (
          <div className="modalOverlay" onClick={() => setOabForm((f) => ({ ...f, open: false }))}>
            <div className="modalCard" onClick={(e) => e.stopPropagation()}>
              <h3>Captura por OAB</h3>
              <label>
                OAB
                <input
                  value={oabForm.oab}
                  onChange={(e) => setOabForm((f) => ({ ...f, oab: e.target.value }))}
                  placeholder="Número da OAB"
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

        {overlay === "settings" ? (
          <SettingsModal
            settings={settings}
            offline={offline}
            onUpdate={updateSettings}
            onReset={resetSettings}
            onClose={() => setOverlay(null)}
          />
        ) : null}

        {overlay === "help" ? (
          <HelpModal connectors={operationalConnectors} onClose={() => setOverlay(null)} />
        ) : null}

        {overlay === "profile" ? (
          <ProfileModal onClose={() => setOverlay(null)} onSignOut={signOut} />
        ) : null}

        {detail ? (
          <DetailDrawer
            selection={detail}
            processos={data.processos}
            intimacoes={data.intimacoes}
            prazos={data.prazos}
            peticoes={data.peticoes}
            busy={busy}
            offline={offline}
            onClose={() => setDetail(null)}
            onSelect={setDetail}
            onGenerateDraft={(intimacaoId) =>
              runAction(`draft-${intimacaoId}`, async () => {
                const cls = await gerarMinuta(intimacaoId, calendarYears);
                if (cls)
                  setLastClassificacao({ intimacaoId, tipo: cls.tipo, confianca: cls.confianca });
              })
            }
            onOpenPeticao={(peticao) => {
              setDetail(null);
              setEditorPeticao(peticao);
            }}
            onEditPrazo={(prazo) => {
              setDetail(null);
              editarPrazo(prazo);
            }}
          />
        ) : null}

        {protocolarTarget ? (
          <ProtocolarModal
            peticao={protocolarTarget}
            processo={
              data.processos.find((p) => p.id === protocolarTarget.processo_id) ?? null
            }
            busy={busy === `file-${protocolarTarget.id}`}
            onConfirm={(credencialId) => void confirmarProtocolo(credencialId)}
            onClose={() => setProtocolarTarget(null)}
          />
        ) : null}

        {editorPeticao ? (
          <MinutaEditor
            peticao={editorPeticao}
            processo={data.processos.find((p) => p.id === editorPeticao.processo_id) ?? null}
            prazo={data.prazos.find((p) => p.id === editorPeticao.prazo_id) ?? null}
            busy={busy === `save-pet-${editorPeticao.id}`}
            onSave={(content) =>
              runAction(`save-pet-${editorPeticao.id}`, async () => {
                const updated = await editarPeticao(editorPeticao.id, { conteudo: content });
                setEditorPeticao(updated);
              })
            }
            onClose={() => setEditorPeticao(null)}
          />
        ) : null}

        {prazoEdit ? (
          <PrazoEditModal
            prazo={prazoEdit}
            busy={busy === `edit-${prazoEdit.id}`}
            onSave={salvarRevisaoPrazo}
            onClose={() => setPrazoEdit(null)}
          />
        ) : null}
      </section>
    </main>
  );
}
