"use client";

import {
  BookOpen,
  CheckCircle2,
  Clock3,
  FilePenLine,
  Loader2,
  Search,
  ShieldCheck,
  UserRound
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  carregarUsuarioAtual,
  CurrentUser,
  DashboardData,
  listarDocumentos,
  listarOabsMonitoradas,
  listarTemplates,
  OabMonitorada,
  TemplatePeticao
} from "@/lib/api";
import { listarTrabalhos } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
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
  const [documentsTotal, setDocumentsTotal] = useState(0);
  const [worksTotal, setWorksTotal] = useState(0);
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
        const [user, monitored, officeTemplates, documents, works] = await Promise.all([
          carregarUsuarioAtual(),
          listarOabsMonitoradas(),
          listarTemplates(),
          listarDocumentos({ limit: 1 }),
          listarTrabalhos()
        ]);
        if (cancelled) return;
        setMe(user);
        setOabs(monitored);
        setTemplates(officeTemplates);
        setDocumentsTotal(documents.total);
        setWorksTotal(works.total);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(humanError(err, "Falha ao carregar o onboarding"));
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
  const hasOab = oabs.some((oab) => oab.ativo);
  const hasCapture = data.intimacoes.length > 0;
  const hasDeadline = data.prazos.length > 0;
  const hasTemplate = templates.some((template) => template.ativo);

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
      title: "Documentos recebidos",
      detail: documentsTotal > 0
        ? `${documentsTotal} documento(s) no escritório. Confira origem, páginas e cobertura antes de redigir.`
        : "Envie os autos disponíveis e os documentos do cliente. Registre o que falta.",
      done: documentsTotal > 0,
      action: "Abrir documentos",
      onClick: () => onNavigate("documentos")
    },
    {
      icon: <FilePenLine size={16} />,
      title: "Trabalho jurídico",
      detail: worksTotal > 0
        ? `${worksTotal} trabalho(s) cadastrado(s), com providência e parte representada.`
        : "Inicie uma providência a partir de uma intimação ou de um processo cadastrado manualmente.",
      done: worksTotal > 0,
      action: "Abrir trabalhos",
      onClick: () => onNavigate("trabalhos")
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
        : "Prepare uma minuta a partir de um trabalho com documentos e fontes conferíveis.",
      done: Boolean(firstDraft),
      action: "Abrir trabalhos",
      onClick: () => onNavigate("trabalhos")
    },
    {
      icon: <ShieldCheck size={16} />,
      title: "Revisão e aprovação",
      detail: approved
        ? "Já existe minuta aprovada pelo advogado."
        : "Aprove a primeira minuta no módulo Revisão e aprovação.",
      done: approved,
      action: "Abrir gate",
      onClick: () => onNavigate("gate")
    }
  ];

  return (
    <section className="onboardingSurface">
      <div className="onboardingHero">
        <div>
          <span className="sectionKicker">Onboarding de piloto</span>
          <h2>Ativacao do primeiro escritorio</h2>
          <p>
            Prepare a entrada do primeiro caso, confira documentos e prazos,
            gere uma minuta e registre a revisão humana.
          </p>
        </div>
        {loading ? <div className="onboardingScore" role="status"><Loader2 className="spin" size={18} /><span>Atualizando etapas</span></div> : null}
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
