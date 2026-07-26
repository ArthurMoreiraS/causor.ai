"use client";

import { KeyRound, Laptop, Loader2, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  loginTribunal,
  proximoPassoContexto,
  ProximoPasso,
  statusSessaoTribunal
} from "@/lib/api";
import { humanError } from "@/lib/errors";
import { useToast } from "./Toast";
import { LoadingButton } from "./ui";

const POLL_MS = 4000;

export type WizardStep = "loading" | "pair_agent" | "court_login" | "capturing" | "ready" | "error";

function stepFromPasso(passo: ProximoPasso): WizardStep {
  if (passo.ready) return "ready";
  if (passo.next_step === "pair_agent") return "pair_agent";
  if (passo.next_step === "court_login") return "court_login";
  return "capturing";
}

/**
 * Assistente JIT de acesso ao tribunal. Encadeia pareamento -> login -> captura
 * e, quando o contexto fica pronto, chama `onReady` (a UI gera a minuta sem
 * novo clique). O login abre o portal na máquina do advogado via agente local.
 */
export default function AcessoTribunalWizard({
  processoId,
  onReady,
  onClose
}: {
  processoId: number;
  onReady: () => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const [step, setStep] = useState<WizardStep>("loading");
  const [passo, setPasso] = useState<ProximoPasso | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await proximoPassoContexto(processoId);
      setPasso(next);
      setStep(stepFromPasso(next));
      if (next.ready) onReady();
    } catch (err) {
      setError(humanError(err, "Falha ao consultar o acesso ao tribunal"));
      setStep("error");
    }
  }, [processoId, onReady]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function abrirLogin() {
    if (!passo) return;
    setBusy(true);
    try {
      await loginTribunal(processoId, passo.rota.grau, passo.rota.sistema);
      toast({
        kind: "info",
        title: "Abrindo o portal no seu computador",
        description: "Faça o login uma vez; o Causor detecta quando você entrar."
      });
      await statusSessaoTribunal(processoId);
      await refresh();
    } catch (err) {
      setError(humanError(err, "Falha ao abrir o login no seu computador"));
    } finally {
      setBusy(false);
    }
  }

  const rotaLabel = passo
    ? `${passo.rota.sistema} · ${passo.rota.tribunal} · ${passo.rota.grau}º grau`
    : "";

  return (
    <section className="acessoWizard" aria-label="Assistente de acesso ao tribunal">
      <header className="acessoWizardHeader">
        <strong>Preparar contexto do processo</strong>
        {rotaLabel && <span className="acessoWizardRota">{rotaLabel}</span>}
      </header>

      {step === "loading" && (
        <p className="acessoWizardStep">
          <Loader2 className="spin" size={14} /> Verificando o acesso…
        </p>
      )}

      {step === "pair_agent" && (
        <div className="acessoWizardStep">
          <p>
            <Laptop size={14} /> Nenhum computador pareado está online. Pareie este
            computador em <strong>Configurações → Acesso aos tribunais</strong> e rode o
            agente para o Causor conseguir abrir o tribunal.
          </p>
          <button className="toolbarButton compact" onClick={() => void refresh()}>
            Já pareei — verificar
          </button>
        </div>
      )}

      {step === "court_login" && (
        <div className="acessoWizardStep">
          <p>
            <KeyRound size={14} /> Entre no tribunal uma vez. Ao clicar, uma janela do
            portal abre no seu computador; faça o login com o certificado e volte aqui.
          </p>
          <LoadingButton
            className="toolbarButton primary compact"
            loading={busy}
            icon={<KeyRound size={14} />}
            onClick={() => void abrirLogin()}
          >
            Abrir portal para login
          </LoadingButton>
        </div>
      )}

      {step === "capturing" && (
        <p className="acessoWizardStep">
          <Loader2 className="spin" size={14} /> Conectado. Baixando a íntegra dos autos e
          montando o contexto… isto continua mesmo se você fechar.
        </p>
      )}

      {step === "ready" && (
        <p className="acessoWizardStep acessoWizardReady">
          <ShieldCheck size={14} /> Contexto completo. Gerando a minuta…
        </p>
      )}

      {step === "error" && (
        <p className="acessoWizardStep vaultError" role="alert">
          {error}
        </p>
      )}

      <footer className="acessoWizardActions">
        <button className="toolbarButton compact" onClick={onClose}>
          Fechar
        </button>
      </footer>
    </section>
  );
}
