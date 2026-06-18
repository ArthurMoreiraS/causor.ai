"use client";

import { CheckCircle2, Clock3, ExternalLink, Loader2, RefreshCcw, Send, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import {
  confirmarProtocoloManual,
  JobExecucao,
  listarJobs,
  Peticao,
  Processo,
  SignatureHandoff
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Empty } from "../components/ui";

/** Pull the (secret-free) signing handoff the job attached at ready_to_sign. */
function extrairHandoff(job: JobExecucao): SignatureHandoff | null {
  const evidence = (job.resultado?.evidence ?? null) as Record<string, unknown> | null;
  const handoff = evidence?.handoff as SignatureHandoff | undefined;
  if (!handoff || typeof handoff.mensagem !== "string") return null;
  return handoff;
}

/** PJe base URL the connector recorded, when automation actually ran. */
function extrairBaseUrl(job: JobExecucao): string | null {
  const evidence = (job.resultado?.evidence ?? null) as Record<string, unknown> | null;
  const baseUrl = evidence?.base_url;
  return typeof baseUrl === "string" && baseUrl ? baseUrl : null;
}

/** Close the loop: the lawyer signed/filed in PJe and registers the protocol. */
function RegistrarProtocoloForm({
  peticaoId,
  credencialId,
  onDone
}: {
  peticaoId: number;
  credencialId?: number;
  onDone: () => void | Promise<void>;
}) {
  const [numero, setNumero] = useState("");
  const [comprovante, setComprovante] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    const protocolo = numero.trim();
    if (protocolo.length < 3) {
      setErr("Informe o número do protocolo (mínimo 3 caracteres).");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await confirmarProtocoloManual(
        peticaoId,
        protocolo,
        comprovante.trim() || undefined,
        credencialId
      );
      await onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Falha ao registrar o protocolo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="registrarProtocolo">
      <label>
        Número do protocolo
        <input
          value={numero}
          onChange={(e) => setNumero(e.target.value)}
          placeholder="ex.: PJE-2026-000123"
          disabled={busy}
        />
      </label>
      <label>
        Comprovante (opcional)
        <input
          value={comprovante}
          onChange={(e) => setComprovante(e.target.value)}
          placeholder="link/URI do comprovante"
          disabled={busy}
        />
      </label>
      {err ? <p className="protocolError">{err}</p> : null}
      <button className="toolbarButton primary compact" onClick={() => void submit()} disabled={busy}>
        {busy ? <Loader2 className="spin" size={14} /> : <Send size={14} />}
        Já assinei — registrar protocolo
      </button>
    </div>
  );
}

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
  refreshKey,
  onChanged
}: {
  peticoes: Peticao[];
  processos: Processo[];
  offline: boolean;
  refreshKey: number;
  onChanged?: () => void | Promise<void>;
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
            PJe assistido prepara até ready_to_sign; sistemas sem conector dedicado usam registro
            operacional com gate humano e eventos de auditoria.
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
          const handoff = extrairHandoff(job);
          // Raw checkpoint only helps non-PJe (fake) jobs; PJe jobs show the handoff.
          const checkpoint =
            !handoff && job.resultado?.checkpoint ? String(job.resultado.checkpoint) : null;
          const baseUrl = extrairBaseUrl(job);
          const credencialId =
            job.payload?.credencial_id != null ? Number(job.payload.credencial_id) : undefined;
          const aguardandoAssinatura =
            handoff != null && peticao != null && peticao.status !== "protocolada";
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
                  <dd className="mono">{comprovante ?? "-"}</dd>
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
              {handoff ? (
                <div className="protocolHandoff">
                  <p className="protocolHandoffMsg">{handoff.mensagem}</p>
                  {handoff.instrucoes.length ? (
                    <ol className="protocolHandoffSteps">
                      {handoff.instrucoes.map((passo, i) => (
                        <li key={i}>{passo}</li>
                      ))}
                    </ol>
                  ) : null}
                  <span className="protocolHandoffMeta mono">
                    assinatura: {handoff.provedor} ({handoff.modo})
                  </span>
                  {baseUrl ? (
                    <a className="toolbarButton compact" href={baseUrl} target="_blank" rel="noreferrer">
                      <ExternalLink size={14} />
                      Abrir PJe/PJeOffice
                    </a>
                  ) : null}
                </div>
              ) : null}
              {aguardandoAssinatura && peticao ? (
                <RegistrarProtocoloForm
                  peticaoId={peticao.id}
                  credencialId={credencialId}
                  onDone={async () => {
                    await reload();
                    await onChanged?.();
                  }}
                />
              ) : null}
              {job.erro ? <p className="protocolError">{job.erro}</p> : null}
            </article>
          );
        })}
        {!jobs.length ? (
          <Empty label="Nenhum protocolo executado ainda - aprove uma minuta no Gate OAB e protocole" />
        ) : null}
      </div>
    </section>
  );
}
