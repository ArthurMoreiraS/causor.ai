"use client";

import { CheckCircle2, Clock3, Loader2, RefreshCcw, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { JobExecucao, listarJobs, Peticao, Processo } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Empty } from "../components/ui";

function jobStatusLabel(status: JobExecucao["status"]) {
  if (status === "queued") return "Na fila";
  if (status === "running") return "Executando";
  if (status === "completed") return "Concluído";
  if (status === "failed") return "Falhou";
  return status;
}

function jobStatusIcon(status: JobExecucao["status"]) {
  if (status === "completed") return <CheckCircle2 size={15} />;
  if (status === "failed") return <XCircle size={15} />;
  if (status === "running") return <Loader2 className="spin" size={15} />;
  return <Clock3 size={15} />;
}

export default function ProtocolosView({
  peticoes,
  processos,
  offline,
  refreshKey
}: {
  peticoes: Peticao[];
  processos: Processo[];
  offline: boolean;
  refreshKey: number;
}) {
  const [jobs, setJobs] = useState<JobExecucao[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setBusy(true);
    try {
      setJobs(await listarJobs({ tipo: "protocolo_peticao" }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar protocolos");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!offline) void reload();
  }, [offline, refreshKey]);

  function contexto(job: JobExecucao) {
    const peticao =
      job.entidade === "peticao"
        ? peticoes.find((p) => p.id === job.entidade_id) ?? null
        : null;
    const processo = peticao
      ? processos.find((p) => p.id === peticao.processo_id) ?? null
      : null;
    return { peticao, processo };
  }

  return (
    <section className="protocolSurface">
      <div className="protocolHead">
        <div>
          <strong>Jobs de protocolo</strong>
          <span className="protocolHint">
            Simulado — conector PJe em desenvolvimento. Cada job preserva o gate humano e gera
            eventos na auditoria.
          </span>
        </div>
        <button className="toolbarButton compact" disabled={offline || busy} onClick={() => void reload()}>
          {busy ? <Loader2 className="spin" size={14} /> : <RefreshCcw size={14} />}
          Atualizar
        </button>
      </div>
      {error ? <div className="notice">{error}</div> : null}
      <div className="protocolList">
        {jobs.map((job) => {
          const { peticao, processo } = contexto(job);
          const comprovante = job.resultado?.protocolo ? String(job.resultado.protocolo) : null;
          const checkpoint = job.resultado?.checkpoint ? String(job.resultado.checkpoint) : null;
          return (
            <article className={`protocolCard ${job.status}`} key={job.id}>
              <header>
                <div>
                  <strong>{peticao?.tipo ?? "Petição"}</strong>
                  <span className="mono">
                    {processo?.numero ?? (peticao ? `Processo #${peticao.processo_id}` : `Job #${job.id}`)}
                  </span>
                </div>
                <span className={`jobStatus ${job.status}`}>
                  {jobStatusIcon(job.status)}
                  {jobStatusLabel(job.status)}
                </span>
              </header>
              <dl className="protocolMeta">
                <div>
                  <dt>Comprovante</dt>
                  <dd className="mono">{comprovante ?? "—"}</dd>
                </div>
                <div>
                  <dt>Executado em</dt>
                  <dd>{formatDate(job.updated_at)}</dd>
                </div>
                <div>
                  <dt>Credencial</dt>
                  <dd>
                    {job.payload?.credencial_id != null
                      ? `vault #${String(job.payload.credencial_id)}`
                      : "não informada"}
                  </dd>
                </div>
              </dl>
              {checkpoint ? <p className="protocolCheckpoint">{checkpoint}</p> : null}
              {job.erro ? <p className="protocolError">{job.erro}</p> : null}
            </article>
          );
        })}
        {!jobs.length ? (
          <Empty label="Nenhum protocolo executado ainda — aprove uma minuta no Gate OAB e protocole" />
        ) : null}
      </div>
    </section>
  );
}
