"use client";

import Image from "next/image";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  Clock3,
  Download,
  FilePenLine,
  HelpCircle,
  HomeIcon,
  Inbox,
  Loader2,
  MessageCircle,
  Scale,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  Workflow,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  CaptureResult,
  cumprirPrazo,
  DashboardData,
  editarPeticao,
  gerarMinuta,
  listarOabsMonitoradas,
  loadDashboard,
  OabMonitorada,
  Peticao,
  Prazo,
  ProposedAction,
  protocolarPeticaoAsync,
  removerOabMonitorada,
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
import RadarBell from "./components/RadarBell";
import { useToast } from "./components/Toast";
import UfSearchSelect from "./components/UfSearchSelect";
import { LoadingButton, Modal, NavGroup, NavItem, Skeleton, ThemeToggle } from "./components/ui";
import AssistantWorkspace from "./views/AssistantWorkspace";
import ConectoresView from "./views/ConectoresView";
import FilaDoDiaView from "./views/FilaDoDiaView";
import GateOabView from "./views/GateOabView";
import HomeDashboard from "./views/HomeDashboard";
import OnboardingView from "./views/OnboardingView";
import ProtocolosView from "./views/ProtocolosView";
import TemplatesView from "./views/TemplatesView";
import IntimacoesView from "./views/IntimacoesView";
import PeticoesView from "./views/PeticoesView";
import PrazosView from "./views/PrazosView";
import ProcessosView from "./views/ProcessosView";
import { useRequireAuth } from "./AuthProvider";
import { CALENDAR_YEARS, useSettings } from "@/lib/settings";
import { humanError } from "@/lib/errors";
import { downloadCsv } from "@/lib/export";
import { BRASIL_UFS } from "@/lib/brasil-ufs";
import { computeDashboardMetrics } from "@/lib/metrics";
import {
  daysUntil,
  matchesQuery,
  passesFilters,
  reviewStatusLabel,
  riscoFromDias,
  riskLabel
} from "@/lib/format";
import {
  buildIntimacaoRows,
  buildProcessoRows,
  buildProcessoRowsFromLists,
  CONNECTORS_FALLBACK,
  mergeById,
  STATUS_MATCH,
  StatusKey,
  VIEW_LABEL,
  ViewKey
} from "@/lib/views";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

const API_BASE_LABEL = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function actionSuccessTitle(key: string) {
  if (key.startsWith("draft-")) return "Minuta gerada";
  if (key.startsWith("approve-")) return "Petição aprovada";
  if (key.startsWith("file-")) return "Protocolo preparado";
  if (key.startsWith("done-")) return "Prazo marcado como cumprido";
  if (key.startsWith("edit-")) return "Prazo atualizado";
  if (key.startsWith("save-pet-")) return "Minuta salva";
  return "Ação concluída";
}

export default function Home() {
  const { loading: authLoading, session, signOut } = useRequireAuth();
  const toast = useToast();
  const [data, setData] = useState<DashboardData>(emptyData);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewKey>("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusKey>("pendentes");
  const [error, setError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [captureContext, setCaptureContext] = useState<{ oab: string; uf: string } | null>(null);
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
  const [oabsMonitoradas, setOabsMonitoradas] = useState<OabMonitorada[]>([]);
  const [oabToRemove, setOabToRemove] = useState<OabMonitorada | null>(null);
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
  const classificacaoAbaixoLimiar = lastClassificacao
    ? lastClassificacao.confianca < settings.confidenceThreshold
    : false;
  const confiancaClassificacaoPct = lastClassificacao
    ? Math.round(lastClassificacao.confianca * 100)
    : 0;
  const limiarConfiancaPct = Math.round(settings.confidenceThreshold * 100);

  const calendarYears = useMemo(() => {
    const y = new Date().getFullYear();
    const n = CALENDAR_YEARS;
    const start = y - Math.floor((n - 1) / 2);
    return Array.from({ length: n }, (_, i) => start + i);
  }, []);

  async function loadOabsMonitoradas() {
    try {
      setOabsMonitoradas(await listarOabsMonitoradas());
    } catch {
      setOabsMonitoradas([]);
    }
  }

  function openOab() {
    const defaultUf = (settings.defaultUf || "SP").toUpperCase();
    const validUf = BRASIL_UFS.some((uf) => uf.sigla === defaultUf) ? defaultUf : "SP";
    setOabForm((f) => ({
      ...f,
      open: true,
      oab: f.oab || settings.defaultOab,
      uf: f.uf || validUf
    }));
    void loadOabsMonitoradas();
  }

  async function refresh() {
    setError(null);
    try {
      setData(await loadDashboard());
      setRefreshTick((tick) => tick + 1);
    } catch (err) {
      setError(humanError(err, "Não foi possível carregar o Causor"));
      setData(emptyData);
    }
  }

  async function runAction(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
      toast({ kind: "success", title: actionSuccessTitle(key) });
    } catch (err) {
      const message = humanError(err, "A ação não foi concluída");
      setError(message);
      toast({ kind: "error", title: "Ação não concluída", description: message });
    } finally {
      setBusy(null);
    }
  }

  async function runCaptureOab() {
    const oab = oabForm.oab.trim();
    const uf = oabForm.uf.trim().toUpperCase();
    setBusy("capture");
    setError(null);
    setCaptureResult(null);
    setCaptureContext({ oab, uf });
    try {
      const result = await rodarCapturaOab(oab, uf);
      setCaptureResult(result);
      setOabForm((f) => ({ ...f, open: false }));
      await loadOabsMonitoradas();
      await refresh();
      toast({
        kind: "success",
        title: "Captura concluída",
        description: `${result.intimacoes_novas} intimações novas, ${result.prazos_registrados} prazos registrados. Processos são enriquecidos ao gerar a minuta.`
      });
    } catch (err) {
      const message = humanError(err, "A captura por OAB não foi concluída");
      setError(message);
      toast({ kind: "error", title: "Captura não concluída", description: message });
    } finally {
      setBusy(null);
    }
  }

  async function removeCapturedOab(oab: OabMonitorada) {
    setBusy(`remove-oab-${oab.id}`);
    setError(null);
    try {
      await removerOabMonitorada(oab.id, true);
      await loadOabsMonitoradas();
      await refresh();
      setOabToRemove(null);
      toast({
        kind: "success",
        title: `OAB ${oab.oab}/${oab.uf} removida`,
        description: "Os dados capturados por ela foram apagados."
      });
    } catch (err) {
      const message = humanError(err, "A OAB não foi removida");
      setError(message);
      toast({ kind: "error", title: "OAB não removida", description: message });
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

  async function confirmarProtocolo() {
    const peticao = protocolarTarget;
    if (!peticao) return;
    await runAction(`file-${peticao.id}`, async () => {
      const job = await protocolarPeticaoAsync(peticao.id);
      const protocolo = job.resultado?.protocolo;
      setLastProtocolo({
        tipo: peticao.tipo,
        protocolo: protocolo
          ? String(protocolo)
          : `Preparado para assinatura · job #${job.id}`
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

  const metrics = useMemo(() => computeDashboardMetrics(data), [data]);

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
      if (view === "prazos") return Boolean(item.prazo);
      if (view === "peticoes" || view === "gate") return Boolean(item.peticao);
      return true;
    });
  }, [reviewQueue, view]);

  const dashboardWorklist = useMemo(
    () => scopedQueue.filter((item) => STATUS_MATCH[statusFilter](item.status)),
    [scopedQueue, statusFilter]
  );

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
    // Prefere o conjunto completo do resumo; cai para /processos capado se ausente.
    const processosSource = data.processosResumo?.items ?? data.processos;
    processosSource.forEach((p) => {
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

  // Pools completados com as entidades já cruzadas pelo servidor (reviewQueue):
  // /prazos e /processos são paginados por chaves diferentes (fatal mais antiga
  // vs. id mais recente), então o join client-side operava em subconjuntos
  // disjuntos. Mesclar o que o reviewQueue já resolveu reconcilia os joins das
  // views de Prazos e Processos sem depender de qual página carregou.
  const prazosPool = useMemo(
    () => mergeById(data.prazos, reviewQueue.map((item) => item.prazo)),
    [data.prazos, reviewQueue]
  );
  const processosPool = useMemo(
    () => mergeById(data.processos, reviewQueue.map((item) => item.processo)),
    [data.processos, reviewQueue]
  );

  const processoRows = useMemo(() => {
    // Fonte de verdade: `/processos/resumo` (já cruzado no servidor, sem teto de
    // paginação — era o que fazia a página contar 195 e o dashboard 200). O join
    // client-side vira só fallback quando o endpoint não responde.
    const base = data.processosResumo
      ? buildProcessoRows(data.processosResumo)
      : buildProcessoRowsFromLists(processosPool, prazosPool, data.intimacoes, data.peticoes);
    return base
      .filter(({ processo, proximoPrazo }) =>
        passesFilters(filters, {
          tribunal: processo.tribunal,
          sistema: processo.sistema,
          risco: proximoPrazo
            ? riscoFromDias(daysUntil(proximoPrazo.data_fatal), proximoPrazo.cumprido)
            : "sem_prazo"
        })
      )
      .filter(({ processo, proximoPrazo, intimacaoTipo, peticaoTipo }) =>
        matchesQuery(
          [
            processo.numero,
            processo.classe,
            processo.tribunal,
            processo.orgao_julgador,
            processo.sistema,
            proximoPrazo?.descricao,
            intimacaoTipo,
            peticaoTipo
          ],
          query
        )
      );
  }, [data.processosResumo, processosPool, prazosPool, data.intimacoes, data.peticoes, query, filters]);

  const intimacaoRows = useMemo(() => {
    // Deriva da fila de revisão do servidor (join intimação↔prazo já correto),
    // em vez de re-cruzar contra /prazos paginado — que fazia intimações com
    // prazo aparecerem como "Pendente".
    return buildIntimacaoRows(reviewQueue)
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
  }, [reviewQueue, query, filters]);

  const prazoRows = useMemo(() => {
    return prazosPool
      .map((prazo) => {
        const processo = processosPool.find((item) => item.id === prazo.processo_id) ?? null;
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
  }, [prazosPool, processosPool, data.intimacoes, data.peticoes, query, filters]);

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
          r.intimacoesCount,
          r.peticoesCount
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
  const operationalConnectors = data.operational?.connectors ?? CONNECTORS_FALLBACK;

  // Identidade real da sessão no rodapé da sidebar (e-mail + iniciais).
  const userEmail = session?.user?.email ?? null;
  const userInitials = userEmail ? userEmail.slice(0, 2).toUpperCase() : "CS";
  const isPilotAccount = userEmail === "causorai@gmail.com";

  // Primeiro nome para a saudação da home (metadata do Supabase; sem fallback
  // para o e-mail — local-part não é nome apresentável).
  const userMeta = (session?.user?.user_metadata ?? {}) as Record<string, unknown>;
  const rawUserName =
    typeof userMeta.nome === "string"
      ? userMeta.nome
      : typeof userMeta.name === "string"
        ? userMeta.name
        : null;
  const greetingName = rawUserName?.trim().split(/\s+/)[0] ?? null;

  if (authLoading || !session) {
    return (
      <div className="authShell authLoadingShell" aria-busy="true" aria-label="Carregando Causor">
        <div className="authLoadingCard">
          <Skeleton height={38} width={150} radius={10} />
          <Skeleton height={14} width="82%" />
          <Skeleton height={14} width="62%" />
          <div className="authLoadingGrid">
            <Skeleton height={78} radius={12} />
            <Skeleton height={78} radius={12} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className={`shell${sidebarCollapsed ? " sidebarCollapsed" : ""}${view === "assistente" ? " assistantShell" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brandLockup" aria-label="Causor" title="Causor">
            <span className="brandArt">
              <Image
                className="brandAssetDark"
                src="/brand/causor-lockup-dark.png"
                alt=""
                fill
                unoptimized
                priority
              />
              <Image
                className="brandAssetLight"
                src="/brand/causor-lockup-light.png"
                alt=""
                fill
                unoptimized
                priority
              />
            </span>
            {isPilotAccount ? <span className="brandTag">Piloto</span> : null}
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
            icon={<HomeIcon size={15} />}
            label="Dashboard"
            active={view === "dashboard"}
            onClick={() => setView("dashboard")}
          />
          <NavItem
            icon={<CheckCircle2 size={15} />}
            label="Onboarding"
            active={view === "onboarding"}
            onClick={() => setView("onboarding")}
          />
          <NavItem
            icon={<MessageCircle size={15} />}
            label="Assistente"
            active={view === "assistente"}
            onClick={() => setView("assistente")}
          />
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
              icon={<Scale size={15} />}
              label="Processos"
              active={view === "processos"}
              onClick={() => setView("processos")}
            />
            <NavItem
              icon={<Inbox size={15} />}
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
            <div className="avatar">{userInitials}</div>
            <div>
              <strong>Conta</strong>
              <span>{userEmail ?? "Usuário do piloto"}</span>
            </div>
            <ChevronDown size={14} />
          </button>
        </div>
      </aside>

      <section className={view === "assistente" ? "workspace assistantWorkspaceHost" : "workspace"}>
        <header className="appbar">
          <div className="crumbs">
            <span>Legal Ops</span>
            <ChevronRight size={13} />
            <strong>{VIEW_LABEL[view]}</strong>
          </div>
          <div className="appActions">
            <ThemeToggle />
            <RadarBell
              offline={offline}
              refreshKey={refreshTick}
              onGoToPrazos={() => setView("prazos")}
            />
            <button className="toolbarButton primary" onClick={openOab} disabled={offline}>
              <Search size={15} />
              Captura por OAB
            </button>
          </div>
        </header>

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
              Captura concluída
              {captureContext ? ` para OAB ${captureContext.oab}/${captureContext.uf}` : ""}:{" "}
              {captureResult.intimacoes_novas} intimações novas e{" "}
              {captureResult.prazos_registrados} prazos registrados. Os dados
              completos do processo são carregados ao gerar a minuta.
            </span>
            <button
              className="dismiss-notice"
              onClick={() => setCaptureResult(null)}
              aria-label="Fechar aviso de captura"
            >
              <X size={16} />
            </button>
          </div>
        ) : null}

        {lastProtocolo ? (
          <div className="notice success">
            <CheckCircle2 size={18} />
            <span>
              Fluxo de protocolo atualizado: {lastProtocolo.tipo ?? "petição"} — referência{" "}
              <strong className="mono">{lastProtocolo.protocolo}</strong>. Registrado na auditoria.
            </span>
            <button
              className="dismiss-notice"
              onClick={() => setLastProtocolo(null)}
              aria-label="Fechar aviso de protocolo"
            >
              <X size={16} />
            </button>
          </div>
        ) : null}

        {lastClassificacao ? (
          <div
            className={
              classificacaoAbaixoLimiar
                ? "notice classificationNotice"
                : "notice success classificationNotice"
            }
          >
            <div className="classificationNoticeIcon" aria-hidden="true">
              {classificacaoAbaixoLimiar ? <AlertTriangle size={18} /> : <Sparkles size={18} />}
            </div>
            <div className="classificationNoticeBody">
              <div className="classificationNoticeEyebrow">Classificação da IA</div>
              <div className="classificationNoticeTitleRow">
                <strong className="classificationNoticeTitle">{lastClassificacao.tipo}</strong>
                <span className="classificationNoticeConfidence">
                  confiança {confiancaClassificacaoPct}%
                </span>
              </div>
              <p className="classificationNoticeText">
                {classificacaoAbaixoLimiar ? (
                  <>
                    Abaixo do limiar operacional de <strong>{limiarConfiancaPct}%</strong>.
                    Revise a peça com atenção antes de seguir para aprovação.
                  </>
                ) : (
                  "Classificação dentro do limiar configurado, pronta para revisão final."
                )}
              </p>
            </div>
            <button
              className="dismiss-notice classificationNoticeDismiss"
              onClick={() => setLastClassificacao(null)}
              aria-label="Fechar aviso de classificação"
            >
              <X size={16} />
            </button>
          </div>
        ) : null}

        {view === "onboarding" ? (
          <OnboardingView
            data={data}
            offline={offline}
            onOpenOab={openOab}
            onNavigate={setView}
            onOpenSettings={() => setOverlay("settings")}
          />
        ) : view === "assistente" ? (
          <AssistantWorkspace
            offline={offline}
            onConfirmAction={confirmAssistantAction}
          />
        ) : view === "templates" ? (
          <TemplatesView offline={offline} />
        ) : view === "protocolos" ? (
          <ProtocolosView
            peticoes={data.peticoes}
            processos={data.processos}
            offline={offline}
            refreshKey={refreshTick}
            onChanged={refresh}
          />
        ) : view === "conectores" ? (
          <ConectoresView
            connectors={operationalConnectors}
            onOpenVault={() => setOverlay("settings")}
          />
        ) : view === "dashboard" ? (
          <HomeDashboard
            metrics={metrics}
            prazoRows={prazoRows.slice(0, 5)}
            operationalConnectors={operationalConnectors}
            offline={offline}
            busy={busy}
            onOpenOab={openOab}
            onOpenAssistant={() => setView("assistente")}
            onNavigate={setView}
            greetingName={greetingName}
            worklistSlot={
              <>
                <section className="statusTabs">
                  <button
                    className={`statusTab ${statusFilter === "pendentes" ? "active" : ""}`}
                    aria-pressed={statusFilter === "pendentes"}
                    onClick={() => setStatusFilter("pendentes")}
                  >
                    <Clock3 size={15} />
                    Pendentes
                    <span className="tabCount">{statusCounts.pendentes}</span>
                  </button>
                  <button
                    className={`statusTab ${statusFilter === "minutadas" ? "active" : ""}`}
                    aria-pressed={statusFilter === "minutadas"}
                    onClick={() => setStatusFilter("minutadas")}
                  >
                    <Sparkles size={15} />
                    Minutadas
                    <span className="tabCount">{statusCounts.minutadas}</span>
                  </button>
                  <button
                    className={`statusTab ${statusFilter === "aprovadas" ? "active" : ""}`}
                    aria-pressed={statusFilter === "aprovadas"}
                    onClick={() => setStatusFilter("aprovadas")}
                  >
                    <CheckCircle2 size={15} />
                    Aprovadas
                    <span className="tabCount">{statusCounts.aprovadas}</span>
                  </button>
                  <button
                    className={`statusTab ${statusFilter === "protocoladas" ? "active" : ""}`}
                    aria-pressed={statusFilter === "protocoladas"}
                    onClick={() => setStatusFilter("protocoladas")}
                  >
                    <Send size={15} />
                    Protocoladas
                    <span className="tabCount">{statusCounts.protocoladas}</span>
                  </button>
                </section>
                <FilaDoDiaView
                  key={statusFilter}
                  items={dashboardWorklist}
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
                  onApprove={(peticao) =>
                    runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))
                  }
                  onFile={protocolar}
                  onNavigate={setView}
                />
              </>
            }
          />
        ) : view === "auditoria" ? (
          <section className="workSurface auditSurface">
            <AuditPanel offline={offline} />
          </section>
        ) : (
        <section className="workSurface">
          <div className="viewbar">
            <div className="viewTitleBlock">
              <h1 className="viewTitle">{VIEW_LABEL[view]}</h1>
              <span className="viewMeta">{viewCount.toLocaleString("pt-BR")} registros</span>
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

          {view === "processos" ? (
            <ProcessosView
              rows={processoRows}
              total={data.processosResumo?.total}
              loaded={data.processosResumo?.items.length}
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

        {oabForm.open ? (
          <div
            className="modalOverlay"
            onClick={() => {
              if (busy !== "capture") setOabForm((f) => ({ ...f, open: false }));
            }}
          >
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
                <UfSearchSelect
                  value={oabForm.uf}
                  disabled={busy === "capture"}
                  onChange={(uf) => setOabForm((f) => ({ ...f, uf }))}
                />
              </label>
              {busy === "capture" ? (
                <div className="captureFeedback" role="status" aria-live="polite">
                  <Loader2 className="spin" size={14} />
                  <span>
                    Capturando intimações para OAB {oabForm.oab.trim() || "informada"}/
                    {oabForm.uf}. Isso pode levar alguns instantes.
                  </span>
                </div>
              ) : null}
              <div className="modalListBlock">
                <strong>OABs monitoradas</strong>
                {oabsMonitoradas.length === 0 ? (
                  <p>Nenhuma OAB cadastrada.</p>
                ) : (
                  <div className="modalListRows">
                    {oabsMonitoradas.map((oab) => (
                      <div className="modalListRow" key={oab.id}>
                        <span>
                          {oab.oab}/{oab.uf}
                        </span>
                        <button
                          className="toolbarButton compact danger"
                          disabled={busy === `remove-oab-${oab.id}`}
                          onClick={() => {
                            setError(null);
                            setOabToRemove(oab);
                          }}
                        >
                          {busy === `remove-oab-${oab.id}` ? (
                            <Loader2 className="spin" size={14} />
                          ) : null}
                          Remover
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="modalActions">
                <button
                  className="toolbarButton"
                  disabled={busy === "capture"}
                  onClick={() => setOabForm((f) => ({ ...f, open: false }))}
                >
                  Cancelar
                </button>
                <LoadingButton
                  className="toolbarButton primary"
                  loading={busy === "capture"}
                  disabled={
                    !oabForm.oab.trim() ||
                    busy === "capture" ||
                    !BRASIL_UFS.some((uf) => uf.sigla === oabForm.uf)
                  }
                  onClick={() => void runCaptureOab()}
                >
                  {busy === "capture" ? "Capturando..." : "Capturar"}
                </LoadingButton>
              </div>
            </div>
          </div>
        ) : null}

        {oabToRemove ? (
          <Modal
            onClose={() => {
              if (!busy?.startsWith("remove-oab-")) setOabToRemove(null);
            }}
            labelledBy="removeCapturedOabTitle"
            className="confirmCard"
          >
            <div className="confirmIcon danger" aria-hidden="true">
              <AlertTriangle size={18} />
            </div>
            <div className="confirmBody">
              <span className="settingsLabel" id="removeCapturedOabTitle">
                Remover OAB {oabToRemove.oab}/{oabToRemove.uf}?
              </span>
              <p>
                Esta ação apaga intimações, prazos, processos e petições capturados por essa OAB.
                A operação não pode ser desfeita.
              </p>
              {error ? (
                <small className="settingsHint vaultError" role="alert">
                  {error}
                </small>
              ) : null}
            </div>
            <div className="modalActions">
              <button
                type="button"
                className="toolbarButton compact"
                disabled={busy?.startsWith("remove-oab-")}
                onClick={() => setOabToRemove(null)}
              >
                Cancelar
              </button>
              <LoadingButton
                className="toolbarButton compact danger confirmDanger"
                loading={busy === `remove-oab-${oabToRemove.id}`}
                icon={<AlertTriangle size={14} />}
                onClick={() => void removeCapturedOab(oabToRemove)}
              >
                Remover definitivamente
              </LoadingButton>
            </div>
          </Modal>
        ) : null}

        {overlay === "settings" ? (
          <SettingsModal
            settings={settings}
            offline={offline}
            onUpdate={updateSettings}
            onReset={resetSettings}
            onOabChanged={refresh}
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
            processos={processosPool}
            intimacoes={data.intimacoes}
            prazos={prazosPool}
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
            onConfirm={() => void confirmarProtocolo()}
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
