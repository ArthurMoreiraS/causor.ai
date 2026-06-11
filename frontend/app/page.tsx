"use client";

import {
  AlertTriangle,
  Bot,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  Download,
  FilePenLine,
  Filter,
  Gavel,
  HelpCircle,
  HomeIcon,
  Loader2,
  LockKeyhole,
  LogOut,
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
  Workflow,
  X
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  CaptureResult,
  ChatTurn,
  cumprirPrazo,
  DashboardData,
  enviarMensagemChat,
  gerarMinuta,
  Intimacao,
  loadDashboard,
  Peticao,
  Prazo,
  Processo,
  ProposedAction,
  protocolarPeticao,
  revisarPrazo,
  ReviewQueueItem,
  rodarCapturaOab
} from "@/lib/api";
import AuditPanel from "./AuditPanel";
import SettingsModal from "./SettingsModal";
import DetailDrawer, { DetailSelection } from "./DetailDrawer";
import MinutaEditor from "./MinutaEditor";
import PrazoEditModal, { PrazoPatch } from "./PrazoEditModal";
import { useSettings } from "@/lib/settings";
import { useLocalDrafts } from "@/lib/drafts";
import { downloadCsv } from "@/lib/export";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

const API_BASE_LABEL = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ViewKey =
  | "inicio"
  | "assistente"
  | "operacao"
  | "processos"
  | "intimacoes"
  | "prazos"
  | "calendario"
  | "peticoes"
  | "gate"
  | "auditoria";

type StatusKey = "pendentes" | "minutadas" | "aprovadas" | "protocoladas";

const STATUS_MATCH: Record<StatusKey, (status: string) => boolean> = {
  pendentes: (s) => s !== "protocolada" && s !== "cumprido",
  minutadas: (s) => s === "minuta_em_revisao",
  aprovadas: (s) => s === "pronta_para_protocolo",
  protocoladas: (s) => s === "protocolada"
};

const VIEW_LABEL: Record<ViewKey, string> = {
  inicio: "Central de Comando",
  assistente: "Assistente Causor",
  operacao: "Agente de Operações Processuais",
  processos: "Processos",
  intimacoes: "Intimações",
  prazos: "Prazos",
  calendario: "Calendário Forense",
  peticoes: "Minutas",
  gate: "Gate OAB",
  auditoria: "Auditoria"
};

const EMPTY_BY_VIEW: Record<ViewKey, string> = {
  inicio: "Nenhuma prioridade encontrada",
  assistente: "Nenhuma conversa iniciada",
  operacao: "Nenhuma intimação encontrada",
  processos: "Nenhum processo encontrado",
  intimacoes: "Nenhuma intimação encontrada",
  prazos: "Nenhum prazo encontrado",
  calendario: "Nenhum vencimento no calendário",
  peticoes: "Nenhuma minuta encontrada",
  gate: "Nenhum item no gate OAB",
  auditoria: "Sem eventos de auditoria"
};

const VIEW_COPY: Record<ViewKey, string> = {
  inicio: "Visão executiva do piloto: prioridades, risco e próximos atos.",
  assistente: "Converse com o agente, consulte o SOR e confirme ações com gate humano.",
  operacao: "Fila integrada de captura, prazo, minuta e gate humano.",
  processos: "Registro dos processos monitorados e seus próximos riscos.",
  intimacoes: "Inbox operacional das comunicações capturadas no DJEN.",
  prazos: "Lista operacional de prazos com revisão e baixa.",
  calendario: "Mapa temporal dos vencimentos forenses e concentração de risco.",
  peticoes: "Ambiente de minuta e revisão de conteúdo antes do gate.",
  gate: "Fila de aprovação humana e protocolo assistido com responsabilidade OAB.",
  auditoria: "Trilha imutável dos atos executados pelo sistema."
};

const workflow = [
  { key: "capture", label: "Captura", detail: "DJEN + DataJud", status: "live" },
  { key: "deadline", label: "Prazo", detail: "Motor determinístico", status: "live" },
  { key: "draft", label: "Minuta", detail: "Claude + templates", status: "review" },
  { key: "approval", label: "Aprovação", detail: "Gate OAB", status: "review" },
  { key: "filing", label: "Protocolo", detail: "PJe / e-SAJ", status: "next" }
];

const connectors = [
  { key: "djen", name: "DJEN", detail: "captura oficial", status: "online" },
  { key: "datajud", name: "DataJud", detail: "andamentos e metadados", status: "online" },
  { key: "pje", name: "PJe", detail: "protocolo assistido", status: "pilot" },
  { key: "esaj", name: "e-SAJ", detail: "próximo conector", status: "planned" }
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

function riskLabel(risco: string) {
  if (risco === "vencido") return "Vencido";
  if (risco === "alto") return "Alto";
  if (risco === "baixo") return "Baixo";
  if (risco === "cumprido") return "Cumprido";
  return "Sem prazo";
}

function matchesQuery(values: Array<string | number | null | undefined>, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return values
    .filter((value) => value !== null && value !== undefined)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

type FilterState = { tribunal: string; sistema: string; risco: string };

function riscoFromDias(dias: number | null, cumprido?: boolean): string {
  if (cumprido) return "cumprido";
  if (dias === null) return "sem_prazo";
  if (dias < 0) return "vencido";
  if (dias <= 3) return "alto";
  if (dias <= 7) return "medio";
  return "baixo";
}

function passesFilters(
  filters: FilterState,
  fields: { tribunal?: string | null; sistema?: string | null; risco?: string | null }
) {
  if (filters.tribunal && fields.tribunal !== filters.tribunal) return false;
  if (filters.sistema && fields.sistema !== filters.sistema) return false;
  if (filters.risco && fields.risco !== filters.risco) return false;
  return true;
}

export default function Home() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewKey>("inicio");
  const [statusFilter, setStatusFilter] = useState<StatusKey>("pendentes");
  const [error, setError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [lastClassificacao, setLastClassificacao] = useState<{
    intimacaoId: number;
    tipo: string;
    confianca: number;
  } | null>(null);
  const [oabForm, setOabForm] = useState<{ open: boolean; oab: string; uf: string }>({
    open: false,
    oab: "",
    uf: "SP"
  });
  const { settings, update: updateSettings, reset: resetSettings } = useSettings();
  const { drafts: localDrafts, save: saveLocalDraft, clear: clearLocalDraft } = useLocalDrafts();
  const [overlay, setOverlay] = useState<null | "settings" | "help" | "profile">(null);
  const [detail, setDetail] = useState<DetailSelection | null>(null);
  const [editorPeticao, setEditorPeticao] = useState<Peticao | null>(null);
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
      if (view === "prazos" || view === "calendario") return Boolean(item.prazo);
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
        : view === "calendario"
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
    } else if (view === "prazos" || view === "calendario") {
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
        </div>

        <nav className="sideNav">
          <NavItem
            icon={<HomeIcon size={15} />}
            label="Início"
            active={view === "inicio"}
            onClick={() => setView("inicio")}
          />
          <NavGroup label="Agentes">
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
            <NavItem
              icon={<FilePenLine size={15} />}
              label="Minutas"
              active={view === "peticoes"}
              onClick={() => setView("peticoes")}
            />
            <NavItem
              icon={<ShieldCheck size={15} />}
              label="Gate OAB"
              active={view === "gate"}
              onClick={() => setView("gate")}
            />
            <NavItem
              icon={<CalendarDays size={15} />}
              label="Calendário Forense"
              active={view === "calendario"}
              onClick={() => setView("calendario")}
            />
          </NavGroup>
          <NavGroup label="Sistema de Registro">
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
            <button className="toolbarButton" onClick={refresh} disabled={loading}>
              {loading ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
              Atualizar
            </button>
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
          {view === "calendario" ? <CalendarioView rows={prazoRows} /> : null}
          {view === "peticoes" ? (
            <PeticoesView
              rows={peticaoRows}
              localDrafts={localDrafts}
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
              onFile={(peticao) => runAction(`file-${peticao.id}`, () => protocolarPeticao(peticao.id))}
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
            onUpdate={updateSettings}
            onReset={resetSettings}
            onClose={() => setOverlay(null)}
          />
        ) : null}

        {overlay === "help" ? (
          <HelpModal connectors={operationalConnectors} onClose={() => setOverlay(null)} />
        ) : null}

        {overlay === "profile" ? (
          <ProfileModal onClose={() => setOverlay(null)} />
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

        {editorPeticao ? (
          <MinutaEditor
            peticao={editorPeticao}
            processo={data.processos.find((p) => p.id === editorPeticao.processo_id) ?? null}
            prazo={data.prazos.find((p) => p.id === editorPeticao.prazo_id) ?? null}
            localDraft={localDrafts[editorPeticao.id]}
            onSaveLocal={(content) => saveLocalDraft(editorPeticao.id, content)}
            onClearLocal={() => clearLocalDraft(editorPeticao.id)}
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

function FiltersPanel({
  filters,
  options,
  onChange,
  onClear,
  onClose
}: {
  filters: FilterState;
  options: { tribunais: string[]; sistemas: string[] };
  onChange: (filters: FilterState) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  const RISCOS = [
    { value: "", label: "Todos" },
    { value: "vencido", label: "Vencido" },
    { value: "alto", label: "Alto" },
    { value: "medio", label: "Médio" },
    { value: "baixo", label: "Baixo" },
    { value: "cumprido", label: "Cumprido" }
  ];
  return (
    <div className="filterPanel" onClick={(e) => e.stopPropagation()}>
      <header>
        <strong>Filtros</strong>
        <button className="iconButton" onClick={onClose} aria-label="Fechar">
          <X size={14} />
        </button>
      </header>
      <label>
        Tribunal
        <select
          value={filters.tribunal}
          onChange={(e) => onChange({ ...filters, tribunal: e.target.value })}
        >
          <option value="">Todos</option>
          {options.tribunais.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        Sistema
        <select
          value={filters.sistema}
          onChange={(e) => onChange({ ...filters, sistema: e.target.value })}
        >
          <option value="">Todos</option>
          {options.sistemas.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label>
        Risco
        <select
          value={filters.risco}
          onChange={(e) => onChange({ ...filters, risco: e.target.value })}
        >
          {RISCOS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
      <footer>
        <button className="toolbarButton compact" onClick={onClear}>
          <Filter size={14} />
          Limpar
        </button>
        <button className="toolbarButton primary" onClick={onClose}>
          Aplicar
        </button>
      </footer>
    </div>
  );
}

function HelpModal({
  connectors,
  onClose
}: {
  connectors: NonNullable<DashboardData["operational"]>["connectors"];
  onClose: () => void;
}) {
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Ajuda</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="settingsGroup">
          <span className="settingsLabel">Como funciona</span>
          <ol className="helpSteps">
            <li><strong>Captura por OAB</strong> — puxa intimações do DJEN e metadados do DataJud.</li>
            <li><strong>Prazo</strong> — calculado por motor determinístico (dias úteis, feriados, recesso).</li>
            <li><strong>Minuta</strong> — a IA classifica e redige; você revisa.</li>
            <li><strong>Gate OAB</strong> — nada é protocolado sem aprovação humana.</li>
          </ol>
        </div>
        <div className="settingsGroup">
          <span className="settingsLabel">Atalhos</span>
          <ul className="helpShortcuts">
            <li><kbd>Enter</kbd> envia mensagem no Assistente</li>
            <li>Botão <strong>Exportar</strong> baixa a lista atual em CSV</li>
            <li>Botão <strong>Filtros</strong> refina por tribunal, sistema e risco</li>
          </ul>
        </div>
        <div className="settingsGroup">
          <span className="settingsLabel">Conectores</span>
          <div className="connectorGrid compactConnectors">
            {connectors.map((c) => (
              <article className={`connector ${c.status}`} key={c.name}>
                <div>
                  <strong>{c.name}</strong>
                  <span>{c.detail}</span>
                </div>
                <small>{connectorStatusLabel(c.status)}</small>
              </article>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProfileModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Conta</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="profileCard">
          <div className="avatar large">AM</div>
          <div>
            <strong>Usuário do piloto</strong>
            <span>Conta de demonstração — autenticação chega numa fase futura.</span>
          </div>
        </div>
        <div className="settingsFooter">
          <button className="toolbarButton" disabled title="Disponível quando a autenticação for implementada">
            <LogOut size={14} />
            Sair (em breve)
          </button>
        </div>
      </div>
    </div>
  );
}

function AssistantWorkspace({
  offline,
  onConfirmAction
}: {
  offline: boolean;
  onConfirmAction: (action: ProposedAction) => Promise<void>;
}) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<ProposedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(textFromSuggestion?: string) {
    const text = (textFromSuggestion ?? input).trim();
    if (!text || busy || offline) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const resp = await enviarMensagemChat(next);
      setTurns([
        ...next,
        {
          role: "assistant",
          content: resp.reply || "Recebi a solicitação e preparei os próximos passos."
        }
      ]);
      setPending(resp.proposed_actions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no assistente");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(action: ProposedAction) {
    setBusy(true);
    setError(null);
    try {
      await onConfirmAction(action);
      setPending((prev) => prev.filter((item) => item !== action));
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: `Ação executada: ${action.label}.` }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ação não concluída");
    } finally {
      setBusy(false);
    }
  }

  const suggestions = [
    "Quais prazos exigem atenção hoje?",
    "Mostre as intimações sem minuta.",
    "Quais minutas aguardam aprovação OAB?"
  ];

  return (
    <section className="assistantWorkspace">
      <div className="chatSurface">
        {turns.length === 0 ? (
          <div className="promptSuggestions">
            {suggestions.map((suggestion) => (
              <button key={suggestion} onClick={() => void send(suggestion)} disabled={offline || busy}>
                <Sparkles size={15} />
                {suggestion}
              </button>
            ))}
          </div>
        ) : (
          <div className="chatTimeline">
            {turns.map((turn, index) => (
              <article className={`chatBubble ${turn.role}`} key={`${turn.role}-${index}`}>
                <span>{turn.content}</span>
              </article>
            ))}
          </div>
        )}

        {pending.length ? (
          <div className="assistantActionShelf">
            {pending.map((action, index) => (
              <article className="assistantActionCard" key={`${action.tipo}-${index}`}>
                <div>
                  <ShieldCheck size={15} />
                  <strong>{action.label}</strong>
                  <span>{action.endpoint}</span>
                </div>
                <div className="proposedActions">
                  <button
                    className="toolbarButton primary"
                    disabled={busy || offline}
                    onClick={() => void confirm(action)}
                  >
                    Confirmar
                  </button>
                  <button
                    className="toolbarButton"
                    disabled={busy}
                    onClick={() => setPending((prev) => prev.filter((item) => item !== action))}
                  >
                    Descartar
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}

        {error ? <div className="assistantError wide">{error}</div> : null}
      </div>

      <form
        className="assistantComposer"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <textarea
          placeholder={offline ? "Backend offline" : "Pergunte ao Causor"}
          value={input}
          disabled={offline || busy}
          rows={1}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <button className="iconButton" disabled={offline || busy || !input.trim()} type="submit">
          {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
        </button>
      </form>
    </section>
  );
}

function QueueTable({
  items,
  busy,
  offline,
  emptyLabel,
  onGenerateDraft,
  onDonePrazo,
  onEditPrazo
}: {
  items: ReviewQueueItem[];
  busy: string | null;
  offline: boolean;
  emptyLabel: string;
  onGenerateDraft: (intimacaoId: number) => void;
  onDonePrazo: (prazo: Prazo) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
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
        {items.map((item) => {
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
                  onClick={() => onGenerateDraft(intimacao.id)}
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
                  onClick={() => (prazo ? onDonePrazo(prazo) : undefined)}
                >
                  {busy === `done-${prazo?.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : (
                    <CheckCircle2 size={15} />
                  )}
                </button>
                <button
                  className="iconButton"
                  title="Editar data fatal"
                  disabled={!prazo || busy === `edit-${prazo?.id}` || offline}
                  onClick={() => (prazo ? void onEditPrazo(prazo) : undefined)}
                >
                  {busy === `edit-${prazo?.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : (
                    <CalendarDays size={15} />
                  )}
                </button>
              </div>
            </article>
          );
        })}
        {!items.length ? <Empty label={emptyLabel} /> : null}
      </div>
    </section>
  );
}

function ProcessosView({
  rows,
  onOpen
}: {
  rows: Array<{
    processo: Processo;
    prazos: Prazo[];
    intimacoes: Intimacao[];
    peticoes: Peticao[];
    proximoPrazo: Prazo | null;
  }>;
  onOpen: (id: number) => void;
}) {
  return (
    <section className="moduleGrid">
      {rows.map(({ processo, prazos, intimacoes, peticoes, proximoPrazo }) => (
        <article
          className="recordCard clickable"
          key={processo.id}
          onClick={() => onOpen(processo.id)}
        >
          <header>
            <div>
              <strong>{processo.numero}</strong>
              <span>{processo.classe ?? "Classe não informada"}</span>
            </div>
            <small>{processo.sistema ?? processo.tribunal ?? "-"}</small>
          </header>
          <div className="recordMeta">
            <span>{processo.orgao_julgador ?? "Órgão não informado"}</span>
            <span>{intimacoes.length} intimações</span>
            <span>{peticoes.length} minutas</span>
          </div>
          <div className="recordFooter">
            <div>
              <span>Próximo prazo</span>
              <strong>{proximoPrazo ? formatDate(proximoPrazo.data_fatal) : "-"}</strong>
            </div>
            <DeadlineBadge prazo={proximoPrazo} />
          </div>
          <div className="recordProgress">
            <span style={{ width: `${Math.min(100, prazos.length * 28 + peticoes.length * 18)}%` }} />
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhum processo encontrado" /> : null}
    </section>
  );
}

function IntimacoesView({
  rows,
  busy,
  offline,
  onOpen,
  onGenerateDraft
}: {
  rows: Array<{
    intimacao: Intimacao;
    processo: Processo | null;
    prazo: Prazo | null;
    peticao: Peticao | null;
  }>;
  busy: string | null;
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onGenerateDraft: (intimacaoId: number) => void;
}) {
  return (
    <section className="inboxList">
      {rows.map(({ intimacao, processo, prazo, peticao }) => (
        <article className="inboxItem clickable" key={intimacao.id} onClick={() => onOpen(intimacao.id)}>
          <div className="inboxMarker">
            <MessageCircle size={15} />
          </div>
          <div className="inboxContent">
            <header>
              <div>
                <strong>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</strong>
                <span>{intimacao.numero_processo ?? processo?.numero ?? "Processo não identificado"}</span>
              </div>
              <small>{formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}</small>
            </header>
            <p>{intimacao.teor ?? "Teor não informado"}</p>
            <div className="inboxMeta">
              <span>{intimacao.tribunal ?? processo?.tribunal ?? "-"}</span>
              <DeadlineBadge prazo={prazo} />
              <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
                {peticao ? statusLabel(peticao.status) : "Sem minuta"}
              </span>
            </div>
          </div>
          <button
            className="toolbarButton"
            disabled={busy === `draft-${intimacao.id}` || offline}
            onClick={(e) => {
              e.stopPropagation();
              onGenerateDraft(intimacao.id);
            }}
          >
            {busy === `draft-${intimacao.id}` ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
            Minutar
          </button>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}

function PrazosView({
  rows,
  busy,
  offline,
  onOpen,
  onDonePrazo,
  onEditPrazo
}: {
  rows: Array<{
    prazo: Prazo;
    processo: Processo | null;
    intimacao: Intimacao | null;
    peticao: Peticao | null;
    dias: number;
  }>;
  busy: string | null;
  offline: boolean;
  onOpen: (sel: DetailSelection) => void;
  onDonePrazo: (prazo: Prazo) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
    <section className="deadlineBoard">
      {rows.map(({ prazo, processo, intimacao, peticao, dias }) => {
        const target: DetailSelection | null = processo
          ? { kind: "processo", id: processo.id }
          : intimacao
            ? { kind: "intimacao", id: intimacao.id }
            : null;
        return (
        <article className="deadlineCard" key={prazo.id}>
          <div className="dateBlock large">
            <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
            <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
          </div>
          <div className="deadlineMain">
            <header>
              <div>
                <strong>{prazo.descricao ?? "Prazo"}</strong>
                <span>{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
              </div>
              <DeadlineBadge prazo={prazo} />
            </header>
            <p>{intimacao?.tipo_comunicacao ?? peticao?.tipo ?? "Ato vinculado não informado"}</p>
            <div className="rowActions">
              {target ? (
                <button className="toolbarButton" onClick={() => onOpen(target)}>
                  <ChevronRight size={15} />
                  Detalhes
                </button>
              ) : null}
              <button
                className="toolbarButton"
                disabled={prazo.cumprido || busy === `done-${prazo.id}` || offline}
                onClick={() => onDonePrazo(prazo)}
              >
                {busy === `done-${prazo.id}` ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
                Cumprir
              </button>
              <button
                className="toolbarButton"
                disabled={busy === `edit-${prazo.id}` || offline}
                onClick={() => void onEditPrazo(prazo)}
              >
                {busy === `edit-${prazo.id}` ? <Loader2 className="spin" size={15} /> : <CalendarDays size={15} />}
                Revisar
              </button>
            </div>
          </div>
        </article>
        );
      })}
      {!rows.length ? <Empty label="Nenhum prazo encontrado" /> : null}
    </section>
  );
}

function CalendarioView({
  rows
}: {
  rows: Array<{
    prazo: Prazo;
    processo: Processo | null;
    intimacao: Intimacao | null;
    peticao: Peticao | null;
    dias: number;
  }>;
}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 14 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() + index);
    const iso = date.toISOString().slice(0, 10);
    const dayRows = rows.filter((row) => row.prazo.data_fatal === iso);
    return { date, iso, rows: dayRows };
  });
  const overdue = rows.filter((row) => row.dias < 0 && !row.prazo.cumprido);
  const week = rows.filter((row) => row.dias >= 0 && row.dias <= 7 && !row.prazo.cumprido);
  const future = rows.filter((row) => row.dias > 7 && !row.prazo.cumprido);

  return (
    <section className="calendarView">
      <div className="calendarRail">
        {days.map((day) => (
          <article className={day.rows.length ? "calendarDay hasItems" : "calendarDay"} key={day.iso}>
            <span>{new Intl.DateTimeFormat("pt-BR", { weekday: "short" }).format(day.date)}</span>
            <strong>{new Intl.DateTimeFormat("pt-BR", { day: "2-digit" }).format(day.date)}</strong>
            <small>{day.rows.length}</small>
          </article>
        ))}
      </div>

      <section className="calendarLanes">
        <CalendarLane title="Vencidos" rows={overdue} tone="risk" />
        <CalendarLane title="Próximos 7 dias" rows={week} tone="warn" />
        <CalendarLane title="Futuros" rows={future} tone="neutral" />
      </section>
    </section>
  );
}

function CalendarLane({
  title,
  rows,
  tone
}: {
  title: string;
  rows: Array<{
    prazo: Prazo;
    processo: Processo | null;
    intimacao: Intimacao | null;
    peticao: Peticao | null;
    dias: number;
  }>;
  tone: "risk" | "warn" | "neutral";
}) {
  return (
    <section className={`calendarLane ${tone}`}>
      <header>
        <strong>{title}</strong>
        <span>{rows.length}</span>
      </header>
      <div>
        {rows.map(({ prazo, processo, dias }) => (
          <article className="calendarEvent" key={prazo.id}>
            <strong>{prazo.descricao ?? "Prazo"}</strong>
            <span>{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
            <small>{dias < 0 ? `${Math.abs(dias)}d vencido` : `${dias}d restantes`}</small>
          </article>
        ))}
        {!rows.length ? <Empty label="Sem eventos" /> : null}
      </div>
    </section>
  );
}

function PeticoesView({
  rows,
  localDrafts,
  onOpenEditor,
  onGoToGate
}: {
  rows: Array<{ peticao: Peticao; processo: Processo | null; prazo: Prazo | null }>;
  localDrafts: Record<number, string>;
  onOpenEditor: (peticao: Peticao) => void;
  onGoToGate: () => void;
}) {
  return (
    <section className="redactionBoard">
      <div className="redactionIntro">
        <FilePenLine size={16} />
        <div>
          <strong>Espaço de redação</strong>
          <span>
            Revise e edite o conteúdo das minutas. A aprovação e o protocolo acontecem no{" "}
            <button className="linkButton" onClick={onGoToGate}>
              Gate OAB
            </button>
            .
          </span>
        </div>
      </div>

      <div className="redactionList">
        {rows.map(({ peticao, processo, prazo }) => {
          const edited = localDrafts[peticao.id] !== undefined;
          const content = localDrafts[peticao.id] ?? peticao.conteudo ?? "Sem conteúdo";
          return (
            <article
              className="redactionCard clickable"
              key={peticao.id}
              onClick={() => onOpenEditor(peticao)}
            >
              <header>
                <div>
                  <strong>{peticao.tipo ?? "Petição"}</strong>
                  <span>{processo?.numero ?? `Processo #${peticao.processo_id}`}</span>
                </div>
                <div className="redactionTags">
                  {edited ? <span className="pill local">Edição local</span> : null}
                  <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
                </div>
              </header>
              <p className="redactionPreview">{content}</p>
              <footer className="redactionFoot">
                <span>{prazo ? `Prazo: ${formatDate(prazo.data_fatal)}` : "Sem prazo vinculado"}</span>
                <span className="redactionOpen">
                  <FilePenLine size={14} />
                  Abrir editor
                </span>
              </footer>
            </article>
          );
        })}
        {!rows.length ? <Empty label="Nenhuma minuta encontrada" /> : null}
      </div>
    </section>
  );
}

function GateOabView({
  rows,
  busy,
  offline,
  onApprove,
  onFile
}: {
  rows: Array<{ peticao: Peticao; processo: Processo | null; prazo: Prazo | null }>;
  busy: string | null;
  offline: boolean;
  onApprove: (peticao: Peticao) => void;
  onFile: (peticao: Peticao) => void;
}) {
  const awaiting = rows.filter((row) => row.peticao.status === "rascunho");
  const cleared = rows.filter((row) => row.peticao.status === "aprovada");
  const filed = rows.filter((row) => row.peticao.status === "protocolada");

  return (
    <section className="gateView">
      <div className="gateSummary">
        <CommandStat label="Aguardando OAB" value={awaiting.length} detail="revisão humana" />
        <CommandStat label="Liberadas" value={cleared.length} detail="prontas para protocolo" />
        <CommandStat label="Protocoladas" value={filed.length} detail="ato finalizado" />
      </div>

      <section className="gateLanes">
        <GateLane
          title="Revisão OAB"
          rows={awaiting}
          busy={busy}
          offline={offline}
          primaryLabel="Aprovar"
          primaryIcon={<CheckCircle2 size={15} />}
          onPrimary={onApprove}
        />
        <GateLane
          title="Liberadas para protocolo"
          rows={cleared}
          busy={busy}
          offline={offline}
          primaryLabel="Protocolar"
          primaryIcon={<Send size={15} />}
          onPrimary={onFile}
          primary
        />
        <GateLane
          title="Protocoladas"
          rows={filed}
          busy={busy}
          offline={offline}
          primaryLabel="Protocolada"
          primaryIcon={<ShieldCheck size={15} />}
          onPrimary={() => undefined}
          readonly
        />
      </section>
    </section>
  );
}

function GateLane({
  title,
  rows,
  busy,
  offline,
  primaryLabel,
  primaryIcon,
  onPrimary,
  primary = false,
  readonly = false
}: {
  title: string;
  rows: Array<{ peticao: Peticao; processo: Processo | null; prazo: Prazo | null }>;
  busy: string | null;
  offline: boolean;
  primaryLabel: string;
  primaryIcon: ReactNode;
  onPrimary: (peticao: Peticao) => void;
  primary?: boolean;
  readonly?: boolean;
}) {
  return (
    <section className="gateLane">
      <header>
        <strong>{title}</strong>
        <span>{rows.length}</span>
      </header>
      <div className="gateLaneBody">
        {rows.map(({ peticao, processo, prazo }) => (
          <article className="gateCard" key={peticao.id}>
            <div>
              <strong>{peticao.tipo ?? "Petição"}</strong>
              <span>{processo?.numero ?? `Processo #${peticao.processo_id}`}</span>
            </div>
            <p>{peticao.conteudo ?? "Sem conteúdo"}</p>
            <small>{prazo ? `Vence em ${formatDate(prazo.data_fatal)}` : "Sem prazo vinculado"}</small>
            <button
              className={primary ? "toolbarButton primary" : "toolbarButton"}
              disabled={readonly || offline || busy === `approve-${peticao.id}` || busy === `file-${peticao.id}`}
              onClick={() => onPrimary(peticao)}
            >
              {primaryIcon}
              {primaryLabel}
            </button>
          </article>
        ))}
        {!rows.length ? <Empty label="Sem itens" /> : null}
      </div>
    </section>
  );
}

function HomeDashboard({
  metrics,
  priorityQueue,
  prazoRows,
  operationalConnectors,
  offline,
  busy,
  onOpenOab,
  onOpenAssistant,
  onNavigate
}: {
  metrics: {
    monitored: number;
    captured: number;
    pending: number;
    highRisk: number;
    drafts: number;
    approved: number;
    overdue: number;
    withoutDraft: number;
    compliance: number;
  };
  priorityQueue: ReviewQueueItem[];
  prazoRows: Array<{
    prazo: Prazo;
    processo: Processo | null;
    intimacao: Intimacao | null;
    peticao: Peticao | null;
    dias: number;
  }>;
  operationalConnectors: NonNullable<DashboardData["operational"]>["connectors"];
  offline: boolean;
  busy: string | null;
  onOpenOab: () => void;
  onOpenAssistant: () => void;
  onNavigate: (view: ViewKey) => void;
}) {
  const nextDeadline = prazoRows.find((row) => !row.prazo.cumprido) ?? null;

  return (
    <section className="homeSurface">
      <section className="homeCommand">
        <div className="commandPanel primaryCommand">
          <div>
            <span className="sectionKicker">Hoje</span>
            <h2>Prioridade operacional</h2>
            <strong>
              {metrics.highRisk > 0
                ? `${metrics.highRisk} prazo${metrics.highRisk > 1 ? "s" : ""} em alto risco`
                : "Nenhum alto risco aberto"}
            </strong>
            <p>
              {nextDeadline
                ? `${nextDeadline.prazo.descricao ?? "Prazo"} vence em ${formatDate(
                    nextDeadline.prazo.data_fatal
                  )}.`
                : "A fila está sem vencimentos pendentes no momento."}
            </p>
          </div>
          <div className="quickActions">
            <button className="toolbarButton primary" onClick={onOpenOab} disabled={busy === "capture" || offline}>
              <Search size={15} />
              Captura por OAB
            </button>
            <button className="toolbarButton" onClick={onOpenAssistant} disabled={offline}>
              <MessageCircle size={15} />
              Assistente
            </button>
          </div>
        </div>

        <div className="commandStats">
          <CommandStat label="Processos" value={metrics.monitored} detail="monitorados" />
          <CommandStat label="Intimações" value={metrics.captured} detail="capturadas" />
          <CommandStat label="Prazos" value={metrics.pending} detail="pendentes" />
          <CommandStat label="Prazos em dia" value={`${metrics.compliance}%`} detail={`${metrics.overdue} vencido(s)`} />
        </div>
      </section>

      <section className="homeGrid">
        <Panel title="Prioridades agora" action={`${priorityQueue.length} itens`}>
          <div className="priorityList">
            {priorityQueue.map((item) => (
              <button
                className="priorityItem"
                key={item.intimacao.id}
                onClick={() => onNavigate(item.prazo ? "prazos" : "intimacoes")}
              >
                <div>
                  <strong>{item.intimacao.numero_processo ?? "Processo não identificado"}</strong>
                  <span>{item.intimacao.tipo_comunicacao ?? "Comunicação judicial"}</span>
                </div>
                <div className="priorityMeta">
                  <small className={`riskText ${item.risco}`}>{riskLabel(item.risco)}</small>
                  <span>{reviewStatusLabel(item.status)}</span>
                </div>
              </button>
            ))}
            {!priorityQueue.length ? <Empty label="Nenhuma prioridade aberta" /> : null}
          </div>
        </Panel>

        <Panel title="Agenda de prazos" action="próximos vencimentos">
          <div className="deadlineAgenda">
            {prazoRows.map(({ prazo, processo, dias }) => (
              <button className="deadlineAgendaItem" key={prazo.id} onClick={() => onNavigate("prazos")}>
                <div className="dateBlock">
                  <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
                  <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
                </div>
                <div>
                  <strong>{prazo.descricao ?? "Prazo"}</strong>
                  <span>{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
                </div>
                <DeadlineBadge prazo={prazo} />
              </button>
            ))}
            {!prazoRows.length ? <Empty label="Nenhum prazo registrado" /> : null}
          </div>
        </Panel>
      </section>

      <section className="homeGrid">
        <Panel title="Saúde operacional" action={offline ? "offline" : "online"}>
          <div className="connectorGrid compactConnectors">
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

        <Panel title="Áreas de trabalho" action="atalhos">
          <div className="featureTiles">
            <FeatureTile icon={<HomeIcon size={16} />} label="Processos" value={metrics.monitored} onClick={() => onNavigate("processos")} />
            <FeatureTile icon={<MessageCircle size={16} />} label="Intimações" value={metrics.captured} onClick={() => onNavigate("intimacoes")} />
            <FeatureTile icon={<Clock3 size={16} />} label="Prazos" value={metrics.pending} onClick={() => onNavigate("prazos")} />
            <FeatureTile icon={<CalendarDays size={16} />} label="Calendário" value={prazoRows.length} onClick={() => onNavigate("calendario")} />
            <FeatureTile icon={<FilePenLine size={16} />} label="Minutas" value={metrics.drafts + metrics.approved} onClick={() => onNavigate("peticoes")} />
            <FeatureTile icon={<ShieldCheck size={16} />} label="Gate OAB" value={metrics.approved} onClick={() => onNavigate("gate")} />
          </div>
        </Panel>
      </section>
    </section>
  );
}

function CommandStat({ label, value, detail }: { label: string; value: ReactNode; detail: string }) {
  return (
    <article className="commandStat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function FeatureTile({
  icon,
  label,
  value,
  onClick
}: {
  icon: ReactNode;
  label: string;
  value: number;
  onClick: () => void;
}) {
  return (
    <button className="featureTile" onClick={onClick}>
      <span>{icon}</span>
      <strong>{label}</strong>
      <small>{value}</small>
    </button>
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
  active = false,
  onClick
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <a
      className={active ? "active" : ""}
      href="#"
      onClick={(e) => {
        e.preventDefault();
        onClick?.();
      }}
    >
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
