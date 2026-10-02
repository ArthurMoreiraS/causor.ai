"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { consultarOperacaoAtual, consultarOperacaoTrabalho, iniciarOperacaoTrabalho, obterTrabalhoAposOperacao,
  type OperacaoTrabalho, type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";

type Pending = { acao: "analise" | "minuta"; versao: number; perguntas: string[]; fontes: number[]; requestId: string };
const keyFor = (id: number) => `causor-work-operation-${id}`;
function readPending(id: number): Pending | null {
  try { return JSON.parse(sessionStorage.getItem(keyFor(id)) || "null") as Pending | null; }
  catch { return null; }
}

export function useWorkOperation(work: Trabalho, onSaved: (work: Trabalho) => void,
                                 onDraftReady: (id: number) => void) {
  const [job, setJob] = useState<OperacaoTrabalho | null>(null);
  const [error, setError] = useState<string | null>(null);
  const currentId = useRef(work.id);
  currentId.current = work.id;
  const currentWork = useRef(work);
  currentWork.current = work;
  const saved = useRef(onSaved);
  saved.current = onSaved;
  const draftReady = useRef(onDraftReady);
  draftReady.current = onDraftReady;
  const processed = useRef<number | null>(null);
  const launched = useRef<string | null>(null);
  const epoch = useRef(0);

  const accept = useCallback(async (next: OperacaoTrabalho, expectedEpoch: number) => {
    if (epoch.current !== expectedEpoch || currentId.current !== next.trabalho_id) return;
    setJob(next);
    if (next.status !== "completed" && next.status !== "failed") return;
    const pending = readPending(next.trabalho_id);
    if (pending && next.request_ids.includes(pending.requestId))
      sessionStorage.removeItem(keyFor(next.trabalho_id));
    if (processed.current === next.id) return;
    if (next.status === "failed") { setError(next.erro || "A operação falhou. Tente novamente."); return; }
    if (next.resultado && currentWork.current.versao < next.resultado.versao) {
      const fresh = await obterTrabalhoAposOperacao(next.trabalho_id);
      if (epoch.current !== expectedEpoch || currentId.current !== next.trabalho_id) return;
      saved.current(fresh);
    }
    processed.current = next.id;
    if (next.acao === "minuta" && next.resultado?.peticao_id && launched.current &&
        next.request_ids.includes(launched.current))
      draftReady.current(next.resultado.peticao_id);
  }, []);

  useEffect(() => {
    let active = true;
    const generation = ++epoch.current;
    processed.current = null;
    launched.current = null;
    setJob(null); setError(null);
    void consultarOperacaoAtual(work.id).then(next => { if (active && next) void accept(next, generation).catch(() => {}); })
      .catch(() => { /* Explicit actions and subsequent polling still use version checks. */ });
    return () => { active = false; epoch.current += 1; };
  }, [work.id, accept]);

  useEffect(() => {
    if (job) return;
    let active = true;
    const generation = epoch.current;
    const timer = setInterval(() => {
      void consultarOperacaoAtual(work.id).then(next => {
        if (active && next) void accept(next, generation).catch(() => {});
      }).catch(() => {});
    }, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [work.id, job, accept]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status) &&
        !(job.status === "completed" && processed.current !== job.id)) return;
    let active = true;
    const generation = epoch.current;
    const timer = setInterval(() => {
      void consultarOperacaoTrabalho(work.id, job.id).then(next => { if (active) void accept(next, generation).catch(() => {}); })
        .catch(() => { /* Keep the same job and try again on the next tick. */ });
    }, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [work.id, job, accept]);

  const start = useCallback(async (acao: "analise" | "minuta", perguntas: string[] = [], fontes: number[] = []) => {
    const workAtStart = currentWork.current;
    const generation = epoch.current;
    const stored = readPending(workAtStart.id);
    const same = stored && stored.acao === acao && stored.versao === workAtStart.versao &&
      JSON.stringify(stored.perguntas) === JSON.stringify(perguntas) && JSON.stringify(stored.fontes) === JSON.stringify(fontes);
    const requestId = same ? stored.requestId : crypto.randomUUID();
    sessionStorage.setItem(keyFor(workAtStart.id), JSON.stringify({ acao, versao: workAtStart.versao,
      perguntas, fontes, requestId } satisfies Pending));
    launched.current = requestId;
    setError(null);
    try {
      const next = await iniciarOperacaoTrabalho(workAtStart, acao, requestId, perguntas, fontes);
      await accept(next, generation);
    } catch (cause) {
      if (epoch.current !== generation || currentId.current !== workAtStart.id) return;
      const unknownOutcome = cause instanceof Error && /Tempo de resposta excedido|Failed to fetch|NetworkError|abort/i.test(cause.message);
      if (unknownOutcome) {
        try {
          const recovered = await consultarOperacaoAtual(workAtStart.id);
          if (recovered && recovered.acao === acao && recovered.versao === workAtStart.versao &&
              recovered.request_ids.includes(requestId)) {
            await accept(recovered, generation);
            return;
          }
        } catch { /* Same request ID remains available for explicit retry. */ }
      }
      setError(humanError(cause, "Não foi possível iniciar a operação."));
    }
  }, [accept]);

  return { job, error, start, clearError: () => setError(null),
    working: job?.status === "queued" || job?.status === "running" };
}
