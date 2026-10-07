"use client";

import "./office.css";

import Image from "next/image";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  Clock3,
  Download,
  HelpCircle,
  Loader2,
  Plus,
  Search,
  Settings,
  SlidersHorizontal,
  Sparkles,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  aprovarPeticao,
  analisarPrazosExistentes,
  CaptureResult,
  cumprirPrazo,
  DashboardData,
  editarPeticao,
  listarOabsMonitoradas,
  loadDashboard,
  OabMonitorada,
  Peticao,
  Prazo,
  ProposedAction,
  removerDadosOab,
  revisarPrazo,
  repetirAnalisePrazo,
  ReviewQueueItem,
  JobExecucao
} from "@/lib/api";
import { useOabCapture } from "./useOabCapture";
import { useDeadlineAnalysis } from "./useDeadlineAnalysis";
import { captureProgress, captureResultFromJob, sameCapture } from "@/lib/oab-capture";
import AuditPanel from "./AuditPanel";
import SidebarNavigation from "./components/SidebarNavigation";
import TarefaDialog from "./components/TarefaDialog";
import ClientesView from "./views/ClientesView";
import TarefasView from "./views/TarefasView";
import DocumentosView from "./views/DocumentosView";
import DocumentEvidenceDialog from "./components/DocumentEvidenceDialog";
import { viewFromHash } from "@/lib/navigation";
import { obterPeticao, type Tarefa, type TarefaInput } from "@/lib/api";
import SettingsModal from "./SettingsModal";
import DetailDrawer, { DetailSelection } from "./DetailDrawer";
import MinutaEditor from "./MinutaEditor";
import PrazoEditModal, { PrazoPatch } from "./PrazoEditModal";
import FiltersPanel from "./components/FiltersPanel";
import HelpModal from "./components/HelpModal";
import ProfileModal from "./components/ProfileModal";
import RadarBell from "./components/RadarBell";
import { useToast } from "./components/Toast";
import UfSearchSelect from "./components/UfSearchSelect";
import { LoadingButton, Modal, NavItem, PageHeader, Skeleton, ThemeToggle } from "./components/ui";
import AssistantWorkspace from "./views/AssistantWorkspace";
import FilaDoDiaView from "./views/FilaDoDiaView";
import GateOabView from "./views/GateOabView";
import HomeDashboard from "./views/HomeDashboard";
import OnboardingView from "./views/OnboardingView";
import TemplatesView from "./views/TemplatesView";
import IntimacoesView from "./views/IntimacoesView";
import PeticoesView from "./views/PeticoesView";
import PrazosView from "./views/PrazosView";
import ProcessosView from "./views/ProcessosView";
import TrabalhosView from "./views/TrabalhosView";
import { obterTrabalho } from "@/lib/work-api";
import { useRequireAuth } from "./AuthProvider";
import { useSettings } from "@/lib/settings";
import { humanError } from "@/lib/errors";
import { downloadCsv } from "@/lib/export";
import { BRASIL_UFS } from "@/lib/brasil-ufs";
import { computeDashboardMetrics } from "@/lib/metrics";
import { captureEmptyMessage, captureFailureMessage } from "@/lib/capture-outcome";
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

const VIEW_COUNT_NOUN: Partial<Record<ViewKey, string>> = {
  processos: "processos",
  intimacoes: "intimações",
  prazos: "prazos",
  peticoes: "minutas",
  gate: "minutas"
};

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
  const [loadingData, setLoadingData] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [view, setCurrentView] = useState<ViewKey>("dashboard");
  const unsavedWork = useRef(false);
  const currentView = useRef<ViewKey>("dashboard");
  const [taskDialog, setTaskDialog] = useState<{ input: TarefaInput; task?: Tarefa; context?: string } | null>(null);
  const [documentContext, setDocumentContext] = useState<{ processId?: number; task?: Tarefa } | null>(null);
  const [evidenceSelection, setEvidenceSelection] = useState<{ id: number; version: number; page: number } | null>(null);
  const setView = useCallback((next: ViewKey) => {
    if (currentView.current === "trabalhos" && next !== "trabalhos" && unsavedWork.current &&
        !window.confirm("Há alterações não salvas no trabalho. Sair e descartá-las?")) return;
    currentView.current = next;
    setCurrentView(next);
    if (window.location.hash !== `#${next}`) window.location.hash = next;
  }, []);
  useEffect(() => {
    const update = () => {
      const next = viewFromHash(window.location.hash);
      if (currentView.current === "trabalhos" && next !== "trabalhos" && unsavedWork.current &&
          !window.confirm("Há alterações não salvas no trabalho. Sair e descartá-las?")) {
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#trabalhos`);
        return;
      }
      currentView.current = next; setCurrentView(next);
    };
    update();
    const params = new URLSearchParams(window.location.search);
    const processId = Number(params.get("processo"));
    const noticeId = Number(params.get("intimacao"));
    const deadlineId = Number(params.get("prazo"));
    if (processId > 0) setWorkProcessId(processId);
    if (noticeId > 0) setWorkOrigin({ intimacaoId: noticeId, prazoId: deadlineId > 0 ? deadlineId : null });
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  function openTask(input: TarefaInput, context?: string) { setTaskDialog({ input, context }); }
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusKey>("pendentes");
  const [error, setError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [captureContext, setCaptureContext] = useState<{ oab: string; uf: string } | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [workProcessId, setWorkProcessId] = useState<number | undefined>();
  const [workOrigin, setWorkOrigin] = useState<{ intimacaoId: number; prazoId: number | null } | undefined>();
  const [newWorkKey, setNewWorkKey] = useState(0);
  const syncWorkRoute = useCallback(() => { setWorkProcessId(undefined); setWorkOrigin(undefined); }, []);
  const [oabForm, setOabForm] = useState<{ open: boolean; oab: string; uf: string }>({
    open: false,
    oab: "",
    uf: ""
  });
  const [oabsMonitoradas, setOabsMonitoradas] = useState<OabMonitorada[]>([]);
  const [oabsLoaded, setOabsLoaded] = useState(false);
  const capture = useOabCapture(session?.user?.id ?? null, () => {
    void loadOabsMonitoradas();
  }, (job: JobExecucao) => {
    const result = captureResultFromJob(job);
    const jobOab = String(job.payload?.oab ?? "");
    const jobUf = String(job.payload?.uf ?? "");
    setCaptureContext({ oab: jobOab, uf: jobUf });
    const empty = job.status === "completed" ? captureEmptyMessage(result, jobOab, jobUf) : null;
    if (empty) {
      // Mantém o modal aberto: o próximo passo provável é corrigir a UF.
      setCaptureResult(result);
      toast({ kind: "error", title: "Nenhuma publicação encontrada", description: empty });
    } else if (job.status === "completed") {
      setCaptureResult(result);
      setOabForm((f) => ({ ...f, open: false }));
      toast({ kind: "success", title: "Captura concluída", description: `${result.intimacoes_novas} intimações novas. Confira a origem e o prazo antes de preparar o trabalho.` });
    } else {
      const message = captureFailureMessage(result) ?? job.erro ?? "A captura não foi concluída.";
      setError(message);
      toast({ kind: "error", title: "Captura não concluída", description: message });
    }
    void refresh();
  }, oabsLoaded ? oabsMonitoradas : undefined);
  const [oabToRemove, setOabToRemove] = useState<{ id?: number; oab: string; uf: string } | null>(null);
  const { settings, update: updateSettings, reset: resetSettings } = useSettings();
  const [overlay, setOverlay] = useState<null | "settings" | "help" | "profile">(null);
  const [detail, setDetail] = useState<DetailSelection | null>(null);
  const [editorPeticao, setEditorPeticao] = useState<Peticao | null>(null);
  const [prazoEdit, setPrazoEdit] = useState<Prazo | null>(null);
  const [backfillProgress, setBackfillProgress] = useState<string | null>(null);
  const [backfillBusy, setBackfillBusy] = useState(false);
  useEffect(() => {
    if (!session?.user?.id) return;
    const cursor = window.localStorage.getItem(`causor-prazo-backfill-${session.user.id}`);
    if (cursor) setBackfillProgress(`Análise interrompida após intimação ${cursor}. Use Continuar análise.`);
  }, [session?.user?.id]);
  const [filters, setFilters] = useState<{ tribunal: string; sistema: string; risco: string }>({
    tribunal: "",
    sistema: "",
    risco: ""
  });
  const [showFilters, setShowFilters] = useState(false);

  const filtersActive = Boolean(filters.tribunal || filters.sistema || filters.risco);


  async function loadOabsMonitoradas() {
    try {
      const rows = await listarOabsMonitoradas();
      setOabsMonitoradas(rows);
      setOabsLoaded(true);
      if (capture.job && !rows.some(row => row.ativo && sameCapture(capture.job!, row.oab, row.uf))) {
        capture.forget(String(capture.job.payload?.oab ?? ""), String(capture.job.payload?.uf ?? ""));
      }
    } catch {
      setError("Não foi possível atualizar as OABs monitoradas.");
    }
  }

  function openOab() {
    const defaultUf = (settings.defaultUf || "").toUpperCase();
    const validUf = BRASIL_UFS.some((uf) => uf.sigla === defaultUf) ? defaultUf : "";
    setOabForm((f) => ({
      ...f,
      open: true,
      oab: capture.job && ["queued", "running"].includes(capture.job.status)
        ? String(capture.job.payload?.oab ?? f.oab) : f.oab || settings.defaultOab,
      uf: capture.job && ["queued", "running"].includes(capture.job.status)
        ? String(capture.job.payload?.uf ?? validUf) : f.uf || validUf
    }));
    void loadOabsMonitoradas();
    if (capture.phase === "lost" || !capture.job) void capture.check();
  }

  async function refresh() {
    setError(null);
    setLoadingData(true);
    try {
      const updated = await loadDashboard();
      setData(updated);
      setRefreshTick((tick) => tick + 1);
      return !updated.backendOffline && !updated.intimacoes.some(item => item.prazo_analise?.status === "analisando");
    } catch (err) {
      setError(humanError(err, "Não foi possível carregar o Causor"));
      setData(previous => ({ ...previous, backendOffline: true }));
      return false;
    } finally { setLoadingData(false); }
  }

  /** `onError` devolve `true` quando a tela já tratou a falha — aí o toast
   * vermelho não aparece. É o que permite o gate de contexto abrir o
   * assistente em vez de virar mensagem de erro. */
  async function runAction(
    key: string,
    action: () => Promise<void>,
    onError?: (err: unknown) => boolean
  ) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
      toast({ kind: "success", title: actionSuccessTitle(key) });
    } catch (err) {
      if (onError?.(err)) return;
      const message = humanError(err, "A ação não foi concluída");
      setError(message);
      toast({ kind: "error", title: "Ação não concluída", description: message });
    } finally {
      setBusy(null);
    }
  }

  function prepareWorkFromNotice(intimacaoId: number, processoId: number | null, prazoId: number | null) {
    if (!processoId) {
      setDetail({ kind: "intimacao", id: intimacaoId });
      toast({ kind: "error", title: "Processo não vinculado", description: "Confira a intimação e vincule o processo antes de preparar o trabalho." });
      return;
    }
    setDetail(null);
    setWorkOrigin({ intimacaoId, prazoId });
    setWorkProcessId(processoId);
    setNewWorkKey(value => value + 1);
    const url = new URL(window.location.href);
    url.searchParams.delete("trabalho");
    url.searchParams.set("novo", "1");
    url.searchParams.set("processo", String(processoId));
    url.searchParams.set("intimacao", String(intimacaoId));
    if (prazoId) url.searchParams.set("prazo", String(prazoId)); else url.searchParams.delete("prazo");
    window.history.replaceState(null, "", url);
    setView("trabalhos");
  }

  async function runCaptureOab() {
    setError(null);
    setCaptureResult(null);
    await capture.submit(oabForm.oab.trim(), oabForm.uf.trim().toUpperCase());
  }

  async function removeCapturedOab(oab: { id?: number; oab: string; uf: string }) {
    setBusy(`remove-oab-${oab.id ?? oab.oab}`);
    setError(null);
    try {
      const result = await removerDadosOab(oab.oab, oab.uf);
      capture.forget(oab.oab, oab.uf);
      setCaptureResult(null); setCaptureContext(null);
      setBackfillProgress(null);
      if (session?.user?.id) window.localStorage.removeItem(`causor-prazo-backfill-${session.user.id}`);
      await loadOabsMonitoradas();
      await refresh();
      setOabToRemove(null);
      toast({
        kind: "success",
        title: `OAB ${oab.oab}/${oab.uf} removida`,
        description: `${result.removidos.intimacoes ?? 0} intimações e ${result.removidos.processos ?? 0} processos removidos.${result.removidos.intimacoes_preservadas ? ` ${result.removidos.intimacoes_preservadas} intimações mantidas por vínculo com outra OAB, trabalho, documento ou prazo confirmado.` : ""}`
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
    if (action.tipo === "abrir_trabalho") {
      const work = await obterTrabalho(Number(payload.trabalho_id));
      const url = new URL(window.location.href); url.searchParams.set("trabalho", String(work.id)); window.history.replaceState(null, "", url);
      setWorkProcessId(work.processo_id || undefined); setView("trabalhos"); return;
    }
    throw new Error("Essa ação não faz parte do MVP. Abra o trabalho e confira as fontes antes de continuar.");
  }

  function editarPrazo(prazo: Prazo) {
    setPrazoEdit(prazo);
  }

  function continueFromPetition(peticao: Peticao) {
    if (peticao.dossie?.trabalho_id) {
      const url = new URL(window.location.href); url.searchParams.set("trabalho", String(peticao.dossie.trabalho_id));
      window.history.replaceState(null, "", url); setWorkProcessId(peticao.processo_id); setView("trabalhos"); return;
    }
    setView("gate");
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

  async function backfillPrazos() {
    const key = `causor-prazo-backfill-${session?.user?.id ?? "unknown"}`;
    setBackfillBusy(true);
    setBackfillProgress("Preparando análise...");
    try {
      let cursor = Number(window.localStorage.getItem(key) ?? "0") || 0;
      let queued = 0;
      let hasMore = false;
      for (let page = 0; page < 20; page++) {
        const batch = await analisarPrazosExistentes(cursor);
        queued += batch.enfileiradas;
        hasMore = batch.ha_mais;
        setBackfillProgress(`${queued} intimações encaminhadas para análise. O processamento ocorre em segundo plano.`);
        if (!batch.ha_mais || batch.ultimo_id <= cursor) break;
        cursor = batch.ultimo_id;
        window.localStorage.setItem(key, String(cursor));
      }
      await refresh();
      if (hasMore) {
        setBackfillProgress(`${queued} análises enfileiradas. Há mais registros; use Continuar análise.`);
      } else {
        window.localStorage.removeItem(key);
        setBackfillProgress(`${queued} análises enfileiradas. Acompanhe os estados nesta lista.`);
      }
    } catch (err) {
      setBackfillProgress("Interrompido. Use Continuar análise; registros já enfileirados serão preservados.");
      toast({ kind: "error", title: humanError(err, "Falha ao enfileirar prazos") });
    } finally {
      setBackfillBusy(false);
    }
  }

  useDeadlineAnalysis(session?.user?.id, data.intimacoes, (states, expected) => {
    const updates = new Map(states.map(item => [item.id, item]));
    setData(previous => {
      const update = (notice: DashboardData["intimacoes"][number]) => {
        const state = updates.get(notice.id);
        if (!state || notice.prazo_analise?.job_id !== expected.get(notice.id)) return notice;
        return { ...notice, prazo_analise: state.prazo_analise };
      };
      return { ...previous, intimacoes: previous.intimacoes.map(update),
        reviewQueue: previous.reviewQueue?.map(item => {
          const intimacao = update(item.intimacao);
          return { ...item, intimacao, status: !item.prazo && !item.peticao
            ? intimacao.prazo_analise?.status ?? "capturada" : item.status };
        }) };
    });
  }, refresh);

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => computeDashboardMetrics(data), [data]);

  const reviewQueue = useMemo<ReviewQueueItem[]>(() => {
    if (data.reviewQueue !== undefined) return data.reviewQueue;
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
            : peticao?.status === "rascunho" || peticao?.status === "em_revisao"
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

  function openNewWork(id?: number) {
    setWorkOrigin(undefined); setWorkProcessId(id); setNewWorkKey(value => value + 1);
    const url = new URL(window.location.href); url.searchParams.delete("trabalho"); url.searchParams.set("novo", "1");
    if (id) url.searchParams.set("processo", String(id)); else url.searchParams.delete("processo");
    url.searchParams.delete("intimacao"); url.searchParams.delete("prazo");
    window.history.replaceState(null, "", url); setView("trabalhos");
  }

  const offline = Boolean(data.backendOffline);
  const operationalConnectors = data.operational?.connectors ?? [];

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
  const captureLabel = capture.job
    ? `OAB ${String(capture.job.payload?.oab ?? "?")}/${String(capture.job.payload?.uf ?? "?")}`
    : "OAB informada";
  const captureVisible = capture.phase === "sending" || (capture.phase === "lost" && !capture.job) ||
    Boolean(capture.job && oabsMonitoradas.some(oab => oab.ativo && sameCapture(capture.job!, oab.oab, oab.uf)));
  const resultVisible = captureContext && oabsMonitoradas.some(oab => oab.ativo &&
    oab.oab === captureContext.oab && oab.uf === captureContext.uf);

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

        <SidebarNavigation view={view} onNavigate={setView} />

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
              Não foi possível atualizar os dados. As informações disponíveis podem estar desatualizadas.
              <button className="toolbarButton compact" disabled={loadingData} onClick={() => void refresh()}>Tentar novamente</button>
              <details><summary>Detalhes da conexão</summary>Servidor: {API_BASE_LABEL}</details>
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        {captureResult && resultVisible && captureContext ? (
          <div className={captureEmptyMessage(captureResult, captureContext.oab, captureContext.uf) ? "notice noticeWithAction" : "notice success noticeWithAction"}>
            {captureEmptyMessage(captureResult, captureContext.oab, captureContext.uf) ? (
              <>
                <AlertTriangle size={18} className="noticeIcon" />
                <div className="noticeBody">
                  <strong>Nenhuma publicação encontrada para a OAB {captureContext.oab}/{captureContext.uf}</strong>
                  <span>{captureEmptyMessage(captureResult, captureContext.oab, captureContext.uf)}</span>
                </div>
                <button type="button" className="toolbarButton compact noticeAction" onClick={openOab}>Corrigir OAB</button>
              </>
            ) : (
              <>
                <CheckCircle2 size={18} className="noticeIcon" />
                <div className="noticeBody">
                  <strong>
                    Captura concluída para a OAB {captureContext.oab}/{captureContext.uf}: {captureResult.intimacoes_novas}{" "}
                    {captureResult.intimacoes_novas === 1 ? "intimação nova" : "intimações novas"}
                  </strong>
                  <span>Os prazos sugeridos exigem conferência em Intimações; os autos dependem dos documentos enviados.</span>
                </div>
                <button type="button" className="toolbarButton compact noticeAction" onClick={() => setView("intimacoes")}>Revisar intimações</button>
              </>
            )}
            <button
              className="dismiss-notice"
              onClick={() => setCaptureResult(null)}
              aria-label="Fechar aviso de captura"
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
        ) : view === "trabalhos" ? (
          <TrabalhosView key={`${workProcessId || "all"}-${workOrigin?.intimacaoId || "manual"}-${newWorkKey}`} processos={data.processos} offline={offline} initialProcessId={workProcessId} initialOrigin={workOrigin} refreshKey={refreshTick} focusOnOpen={newWorkKey > 0} onUnsavedChange={value => { unsavedWork.current = value; }} onRouteChange={syncWorkRoute}
            onChanged={() => void refresh()} onDocuments={id => { setDocumentContext({ processId: id }); setView("documentos"); }}
            onOpenDraft={id => { void obterPeticao(id).then(setEditorPeticao).catch(err => toast({ kind: "error", title: humanError(err, "Falha ao abrir a minuta") })); }} />
        ) : view === "clientes" ? (
          <ClientesView offline={offline} processos={data.processos} refreshKey={refreshTick} onChanged={() => void refresh()}
            onOpenProcess={id => setDetail({ kind: "processo", id })} onNewTask={openTask} />
        ) : view === "tarefas" ? (
          <TarefasView offline={offline} refreshKey={refreshTick} onNew={() => openTask({ titulo: "" })}
            onEdit={task => setTaskDialog({ input: task, task })}
            onDocuments={task => { setDocumentContext({ task }); setView("documentos"); }}
            onOpenProcess={id => setDetail({ kind: "processo", id })}
            onOpenNotice={id => setDetail({ kind: "intimacao", id })}
            onOpenDraft={id => { void obterPeticao(id).then(setEditorPeticao).catch(err => toast({ kind: "error", title: humanError(err, "Falha ao abrir a minuta") })); }} />
        ) : view === "templates" ? (
          <TemplatesView offline={offline} />
        ) : view === "documentos" ? (
          <DocumentosView key={`${documentContext?.processId || "all"}-${documentContext?.task?.id || "none"}`}
            processos={data.processos} offline={offline} initialProcessId={documentContext?.processId} initialTask={documentContext?.task}
            onChanged={() => setRefreshTick(v => v + 1)} onTasks={() => setView("tarefas")} onAll={() => setDocumentContext(null)} />
        ) : view === "dashboard" ? (
          <HomeDashboard
            metrics={metrics}
            unlinkedNotices={data.intimacoes.filter(item => !prazosPool.some(prazo => prazo.intimacao_id === item.id)).length}
            prazoRows={prazoRows}
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
                </section>
                <FilaDoDiaView
                  key={statusFilter}
                  items={dashboardWorklist}
                  offline={offline}
                  onPrepareWork={item => prepareWorkFromNotice(item.intimacao.id, item.processo?.id ?? item.intimacao.processo_id, item.prazo?.id ?? null)}
                  onOpenEditor={(peticao) => setEditorPeticao(peticao)}
                  onNavigate={setView}
                />
              </>
            }
          />
        ) : view === "auditoria" ? (
          <section className="workSurface auditSurface">
            <PageHeader title="Histórico de ações" description="Registro imutável das ações de pessoas e do agente no escritório." />
            <AuditPanel offline={offline} />
          </section>
        ) : (
        <section className="workSurface">
          <PageHeader
            title={VIEW_LABEL[view]}
            description={`${viewCount.toLocaleString("pt-BR")} ${VIEW_COUNT_NOUN[view] ?? "registros"}`}
            actions={<>
              <label className="search">
                <Search size={15} />
                <input
                  placeholder="Buscar processo, tribunal ou ato"
                  aria-label="Buscar processo, tribunal ou ato"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <div className="filterWrap">
                <button
                  className={`toolbarButton ${filtersActive ? "accentOn" : ""}`}
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
              <button className="toolbarButton" onClick={exportCurrentView}>
                <Download size={15} />
                Exportar
              </button>
              {view === "processos" ? (
                <button className="toolbarButton primary" disabled={offline} onClick={() => openNewWork()}>
                  <Plus size={15} />
                  Novo processo ou trabalho
                </button>
              ) : null}
            </>}
          />

          {view === "processos" ? (
            <ProcessosView
              onPrepareWork={openNewWork}
              rows={processoRows}
              total={data.processosResumo?.total}
              loaded={data.processosResumo?.items.length}
              onOpen={(id) => setDetail({ kind: "processo", id })}
            />
          ) : null}
          {view === "intimacoes" ? (
            <IntimacoesView
              rows={intimacaoRows}
              offline={offline}
              onBackfill={() => void backfillPrazos()}
              backfillProgress={backfillProgress}
              backfillBusy={backfillBusy}
              onRetry={id => { void repetirAnalisePrazo(id).then(() => refresh()).catch(err => toast({ kind: "error", title: humanError(err, "Falha ao repetir análise") })); }}
              onOpen={(id) => setDetail({ kind: "intimacao", id })}
              onPrepareWork={prepareWorkFromNotice}
              onCreateTask={intimacao => openTask({ titulo: "", intimacao_id: intimacao.id, tipo: "providencia" }, intimacao.numero_processo || "Intimação selecionada")}
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
              onOpenEditor={setEditorPeticao}
            />
          ) : null}
        </section>
        )}

        {oabForm.open ? (
          <div
            className="modalOverlay"
            onClick={() => setOabForm((f) => ({ ...f, open: false }))}
          >
            <div className="modalCard" onClick={(e) => e.stopPropagation()}>
              <h3>Captura por OAB</h3>
              <label>
                OAB
                <input
                  value={oabForm.oab}
                  disabled={capture.phase === "sending"}
                  onChange={(e) => setOabForm((f) => ({ ...f, oab: e.target.value }))}
                  placeholder="Número da OAB"
                />
              </label>
              <label>
                UF
                <UfSearchSelect
                  placeholder="Selecione a UF da inscrição"
                  value={oabForm.uf}
                  disabled={capture.phase === "sending"}
                  onChange={(uf) => setOabForm((f) => ({ ...f, uf }))}
                />
              </label>
              {captureVisible && capture.phase !== "idle" ? (
                <div className="captureFeedback" role="status" aria-live="polite">
                  {["sending", "queued", "running"].includes(capture.phase) ? <Loader2 className="spin" size={14} aria-hidden="true" /> : null}
                  <span>
                    {capture.phase === "sending" ? "Registrando OAB e solicitando captura..." : null}
                    {capture.phase === "queued" ? `${captureLabel}: aguardando início da consulta.` : null}
                    {capture.phase === "running" ? `${captureLabel}: consulta em andamento. ${capture.job ? captureProgress(capture.job) ?? "Aguardando confirmação do primeiro período." : ""}` : null}
                    {capture.phase === "completed" && capture.job
                      ? captureEmptyMessage(captureResultFromJob(capture.job), String(capture.job.payload?.oab ?? ""), String(capture.job.payload?.uf ?? ""))
                        ?? `${captureLabel}: captura concluída, ${captureResultFromJob(capture.job).intimacoes_novas} intimações novas. Acompanhe a análise de prazos em Intimações.`
                      : null}
                    {capture.phase === "failed" && capture.job ? `${captureLabel}: captura falhou. ${captureFailureMessage(captureResultFromJob(capture.job)) ?? capture.job.erro ?? "Consulte o histórico."}` : null}
                    {capture.phase === "lost" ? `Acompanhamento interrompido${capture.job ? ` para ${captureLabel}` : ""}. ${capture.trackingError ?? "Verifique novamente; o trabalho pode continuar no servidor."}` : null}
                    {capture.phase === "queued" && capture.job && capture.now - new Date(capture.job.created_at).getTime() > 30000 ? " A consulta ainda não começou. Você pode fechar e acompanhar depois." : null}
                    {capture.phase === "running" && capture.job && capture.now - new Date(capture.job.updated_at).getTime() > 30000 ? " Ainda não há progresso confirmado. Você pode fechar e acompanhar depois." : null}
                  </span>
                </div>
              ) : null}
              {captureVisible && capture.phase !== "idle" && capture.phase !== "sending" ? (
                <button className="toolbarButton compact" onClick={() => void capture.check()}>Verificar agora</button>
              ) : null}
              {error ? <small className="settingsHint vaultError" role="alert">{error}</small> : null}
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
                          Remover OAB e dados
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {oabForm.oab.trim() && !oabsMonitoradas.some(item => item.oab === oabForm.oab.trim() && item.uf === oabForm.uf) ? (
                <button type="button" className="toolbarButton compact danger" disabled={Boolean(busy) || capture.phase === "sending"}
                  onClick={() => { setError(null); setOabToRemove({ oab: oabForm.oab.trim(), uf: oabForm.uf }); }}>
                  Remover dados desta OAB
                </button>
              ) : null}
              <div className="modalActions">
                <button
                  className="toolbarButton"
                  onClick={() => setOabForm((f) => ({ ...f, open: false }))}
                >
                  Fechar
                </button>
                <LoadingButton
                  className="toolbarButton primary"
                  loading={capture.phase === "sending"}
                  disabled={
                    !oabForm.oab.trim() ||
                    capture.phase === "sending" ||
                    (["queued", "running"].includes(capture.phase) && capture.job != null &&
                      String(capture.job.payload?.oab) === oabForm.oab.trim() && String(capture.job.payload?.uf) === oabForm.uf) ||
                    !BRASIL_UFS.some((uf) => uf.sigla === oabForm.uf)
                  }
                  onClick={() => void runCaptureOab()}
                >
                  {capture.phase === "sending" ? "Registrando..." : "Capturar"}
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
                Remover OAB {oabToRemove.oab}/{oabToRemove.uf} e dados capturados?
              </span>
              <p>
                O monitoramento será encerrado e os dados exclusivos da captura serão removidos.
                Casos com trabalhos, minutas, documentos ou prazos confirmados, além de registros
                compartilhados com outra OAB monitorada, serão preservados. A exclusão não pode ser desfeita.
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
                loading={busy === `remove-oab-${oabToRemove.id ?? oabToRemove.oab}`}
                icon={<AlertTriangle size={14} />}
                onClick={() => void removeCapturedOab(oabToRemove)}
              >
                Remover OAB e dados
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
            onOabChanged={async () => { setCaptureResult(null); setCaptureContext(null); await loadOabsMonitoradas(); await refresh(); }}
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
            onCreateTask={() => openTask(detail.kind === "processo" ? { titulo: "", processo_id: detail.id } : { titulo: "", intimacao_id: detail.id })}
            onDocuments={() => { const id = detail.kind === "processo" ? detail.id : data.intimacoes.find(i => i.id === detail.id)?.processo_id;
              setDocumentContext(id ? { processId: id } : null); setDetail(null); setView("documentos"); }}
            onSelect={setDetail}
            onPrepareWork={prepareWorkFromNotice}
            onOpenPeticao={(peticao) => {
              setDetail(null);
              setEditorPeticao(peticao);
            }}
            onEditPrazo={(prazo) => {
              setDetail(null);
              editarPrazo(prazo);
            }}
            onPrazoConfirmed={() => { void refresh(); }}
          />
        ) : null}

        {editorPeticao ? (
          <MinutaEditor
            key={editorPeticao.id}
            peticao={editorPeticao}
            processo={data.processos.find((p) => p.id === editorPeticao.processo_id) ?? null}
            prazo={data.prazos.find((p) => p.id === editorPeticao.prazo_id) ?? null}
            busy={busy === `save-pet-${editorPeticao.id}`}
            onOpenEvidence={(id, version, page) => setEvidenceSelection({ id, version, page })}
            onCreateTask={(alerta, index) => openTask({ titulo: "Conferir pendência da minuta", descricao: alerta,
              tipo: "revisao", processo_id: editorPeticao.processo_id, peticao_id: editorPeticao.id,
              alerta_indice: index, alerta_texto_esperado: alerta }, "Pendência identificada na revisão da minuta")}
            onSave={async (content) => {
              setBusy(`save-pet-${editorPeticao.id}`);
              try {
                const updated = await editarPeticao(editorPeticao.id, { conteudo: content });
                setEditorPeticao(updated);
                await refresh();
                toast({ kind: "success", title: "Minuta salva" });
                return true;
              } catch (err) {
                toast({ kind: "error", title: humanError(err, "Não foi possível salvar a minuta") });
                return false;
              } finally { setBusy(null); }
            }}
            onContinue={() => {
              continueFromPetition(editorPeticao);
              setEditorPeticao(null);
            }}
            onClose={() => setEditorPeticao(null)}
          />
        ) : null}

        {evidenceSelection ? <DocumentEvidenceDialog key={`${evidenceSelection.id}-${evidenceSelection.version}`}
          documentoId={evidenceSelection.id} nome={`Documento DOC-${evidenceSelection.id}`} versaoId={evidenceSelection.version}
          pagina={evidenceSelection.page} onClose={() => setEvidenceSelection(null)} /> : null}

        {taskDialog ? <TarefaDialog key={taskDialog.task?.id ?? "new-task"} initial={taskDialog.input} task={taskDialog.task}
          contextLabel={taskDialog.context} processos={data.processos} offline={offline} onClose={() => setTaskDialog(null)}
          onSaved={() => { setTaskDialog(null); setRefreshTick(value => value + 1); toast({ title: "Tarefa disponível em Tarefas e pendências" }); }} /> : null}

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
