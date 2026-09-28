import type { CaptureResult, JobExecucao } from "./api";

export type CapturePhase = "idle" | "sending" | "queued" | "running" | "completed" | "failed" | "lost";

export function captureResultFromJob(job: JobExecucao): CaptureResult {
  const result = job.resultado ?? {};
  const count = (key: string) => typeof result[key] === "number" ? Number(result[key]) : 0;
  return {
    intimacoes_novas: count("intimacoes_novas"),
    processos_enriquecidos: count("processos_enriquecidos"),
    prazos_registrados: count("prazos_registrados"),
    prazos_historicos: count("prazos_historicos"),
    djen_indisponivel: Boolean(result.djen_indisponivel),
    djen_erro: typeof result.djen_erro === "string" ? result.djen_erro : null
  };
}

export function capturePhase(job: JobExecucao): CapturePhase {
  if (job.status === "queued" || job.status === "running" || job.status === "completed" || job.status === "failed") {
    return job.status;
  }
  return "lost";
}

export function captureProgress(job: JobExecucao): string | null {
  const done = job.resultado?.windows_done;
  const total = job.resultado?.windows_total;
  if (typeof done !== "number" || typeof total !== "number" || total <= 0) return null;
  return `${done} de ${total} períodos consultados`;
}

export function sameCapture(job: JobExecucao, oab: string, uf: string): boolean {
  return String(job.payload?.oab ?? "").toUpperCase() === oab.replace(/[\s.\-/]/g, "").toUpperCase()
    && String(job.payload?.uf ?? "").toUpperCase() === uf.trim().toUpperCase();
}
