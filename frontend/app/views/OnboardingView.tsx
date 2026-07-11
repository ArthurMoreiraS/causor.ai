"use client";

import {
  BookOpen,
  CheckCircle2,
  Clock3,
  FilePenLine,
  Loader2,
  Search,
  Send,
  ShieldCheck,
  UserRound,
  Workflow
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  carregarUsuarioAtual,
  CurrentUser,
  DashboardData,
  listarOabsMonitoradas,
  listarTemplates,
  OabMonitorada,
  TemplatePeticao
} from "@/lib/api";
import type { ViewKey } from "@/lib/views";

function statusLabel(done: boolean, blocked = false) {
  if (done) return "Concluido";
  if (blocked) return "Pendente";
  return "Proximo";
}

export default function OnboardingView({
  data,
  offline,
  onOpenOab,
  onNavigate,
  onOpenSettings
}: {
  data: DashboardData;
  offline: boolean;
  onOpenOab: () => void;
  onNavigate: (view: ViewKey) => void;
  onOpenSettings: () => void;
}) {
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [oabs, setOabs] = useState<OabMonitorada[]>([]);
  const [templates, setTemplates] = useState<TemplatePeticao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (offline) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const [user, monitored, officeTemplates] = await Promise.all([
          carregarUsuarioAtual(),
          listarOabsMonitoradas(),
          listarTemplates()
        ]);
        if (cancelled) return;
        setMe(user);
        setOabs(monitored);
        setTemplates(officeTemplates);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Falha ao carregar onboarding");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [offline]);

  const firstDraft = data.peticoes.find((p) => p.status === "rascunho" || p.status === "em_revisao");
  const approved = data.peticoes.some((p) => p.status === "aprovada" || p.status === "protocolada");
  const filed = data.peticoes.some((p) => p.status === "protocolada");
  const hasOab = oabs.some((oab) => oab.ativo);
  const hasCapture = data.intimacoes.length > 0;
  const hasDeadline = data.prazos.length > 0;
  const hasTemplate = templates.some((template) => template.ativo);

  const progress = useMemo(() => {
    const checks = [Boolean(me), hasOab, hasCapture, hasDeadline, hasTemplate, Boolean(firstDraft), approved];
    return Math.round((checks.filter(Boolean).length / checks.length) * 100);
  }, [approved, firstDraft, hasCapture, hasDeadline, hasOab, hasTemplate, me]);

  const steps = [
    {
      icon: <UserRound size={16} />,
      title: "Conta e escritorio",
      detail: me
        ? `Usuario #${me.usuario_id} no escritorio #${me.escritorio_id}`
        : "Crie o usuario no Supabase Auth e rode provision-pilot.",
      done: Boolean(me),
      action: "Ver perfil",
      onClick: onOpenSettings
    },
    {
      icon: <Search size={16} />,
      title: "OAB monitorada",
      detail: hasOab
        ? `${oabs.filter((oab) => oab.ativo).length} OAB(s) ativa(s) para captura`
        : "Cadastre a primeira OAB e rode a captura inicial.",
      done: hasOab,
      action: "Captura por OAB",
      onClick: onOpenOab
    },
    {
      icon: <Clock3 size={16} />,
      title: "Fila inicial",
      detail: hasCapture
        ? `${data.intimacoes.length} intimacao(oes), ${data.prazos.length} prazo(s)`
        : "A captura inicial ainda nao populou a fila.",
      done: hasCapture && hasDeadline,
      action: "Ver prazos",
      onClick: () => onNavigate(hasCapture ? "prazos" : "intimacoes")
    },
    {
      icon: <BookOpen size={16} />,
      title: "Templates do escritorio",
      detail: hasTemplate
        ? `${templates.filter((template) => template.ativo).length} template(s) ativo(s)`
        : "Crie ao menos um modelo recorrente de peca.",
      done: hasTemplate,
      action: "Abrir templates",
      onClick: () => onNavigate("templates")
    },
    {
      icon: <FilePenLine size={16} />,
      title: "Primeira minuta",
      detail: firstDraft
        ? `${firstDraft.tipo ?? "Minuta"} em ${firstDraft.status}`
        : "Gere uma minuta a partir de uma intimacao capturada.",
      done: Boolean(firstDraft),
      action: "Ver intimacoes",
      onClick: () => onNavigate("intimacoes")
    },
    {
      icon: <ShieldCheck size={16} />,
      title: "Gate OAB",
      detail: approved
        ? "Ja existe minuta aprovada ou protocolada."
        : "Aprove a primeira minuta revisada no Gate OAB.",
      done: approved,
      action: "Abrir gate",
      onClick: () => onNavigate("gate")
    },
    {
      icon: <Send size={16} />,
      title: "Protocolo assistido",
      detail: filed
        ? "Ja existe protocolo registrado."
        : "Prepare PJe ate ready_to_sign e registre o numero final.",
      done: filed,
      action: "Ver protocolos",
      onClick: () => onNavigate("protocolos")
    },
    {
      icon: <Workflow size={16} />,
      title: "Acesso aos tribunais",
      detail:
        "Pareie o computador do advogado; o login do tribunal abre pelo assistente ao gerar a minuta e serve leitura e protocolo.",
      done: false,
      action: "Conectores",
      onClick: () => onNavigate("conectores")
    }
  ];

  return (
    <section className="onboardingSurface">
      <div className="onboardingHero">
        <div>
          <span className="sectionKicker">Onboarding de piloto</span>
          <h2>Ativacao do primeiro escritorio</h2>
          <p>
            Use este checklist para sair de conta provisionada ate primeira fila,
            minuta, gate e protocolo assistido.
          </p>
        </div>
        <div className="onboardingScore">
          {loading ? <Loader2 className="spin" size={18} /> : <strong>{progress}%</strong>}
          <span>ativacao</span>
        </div>
      </div>

      {offline ? <div className="notice">Backend offline. O onboarding precisa da API.</div> : null}
      {error ? <div className="notice">{error}</div> : null}

      <div className="onboardingGrid">
        {steps.map((step) => (
          <article className={`onboardingStep ${step.done ? "done" : ""}`} key={step.title}>
            <header>
              <span className="onboardingIcon">{step.done ? <CheckCircle2 size={16} /> : step.icon}</span>
              <small>{statusLabel(step.done, offline)}</small>
            </header>
            <strong>{step.title}</strong>
            <p>{step.detail}</p>
            <button className="toolbarButton compact" disabled={offline} onClick={step.onClick}>
              {step.action}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
