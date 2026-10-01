"use client";

import { CalendarDays, FilePenLine, X } from "lucide-react";
import { useMemo, type ReactNode } from "react";
import type { Intimacao, Peticao, Prazo, Processo } from "@/lib/api";
import { formatDate, statusLabel } from "@/lib/format";
import { sanitizeHtml } from "@/lib/sanitize";
import ConfirmarPrazo from "./components/ConfirmarPrazo";

export type DetailSelection =
  | { kind: "processo"; id: number }
  | { kind: "intimacao"; id: number };

export default function DetailDrawer({
  selection,
  processos,
  intimacoes,
  prazos,
  peticoes,
  busy,
  offline,
  onClose,
  onCreateTask,
  onDocuments,
  onSelect,
  onPrepareWork,
  onOpenPeticao,
  onEditPrazo,
  onPrazoConfirmed
}: {
  selection: DetailSelection;
  processos: Processo[];
  intimacoes: Intimacao[];
  prazos: Prazo[];
  peticoes: Peticao[];
  busy: string | null;
  offline: boolean;
  onClose: () => void;
  onCreateTask?: () => void;
  onDocuments?: () => void;
  onSelect: (sel: DetailSelection) => void;
  onPrepareWork: (intimacaoId: number, processoId: number | null, prazoId: number | null) => void;
  onOpenPeticao: (peticao: Peticao) => void;
  onEditPrazo: (prazo: Prazo) => void;
  onPrazoConfirmed?: (prazo: Prazo) => void;
}) {
  const processo =
    selection.kind === "processo" ? processos.find((p) => p.id === selection.id) ?? null : null;
  const intimacao =
    selection.kind === "intimacao" ? intimacoes.find((i) => i.id === selection.id) ?? null : null;

  return (
    <div className="drawerOverlay" onClick={onClose}>
      <aside className="detailDrawer" onClick={(e) => e.stopPropagation()}>
        <header className="detailDrawerHead">
          {onCreateTask ? <button className="toolbarButton compact" disabled={offline} onClick={onCreateTask}>Nova tarefa</button> : null}
          {onDocuments ? <button className="toolbarButton compact" onClick={onDocuments}>Documentos e evidências</button> : null}
          <span className="sectionKicker">
            {selection.kind === "processo" ? "Processo" : "Intimação"}
          </span>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>

        {processo ? (
          <ProcessoDetail
            processo={processo}
            intimacoes={intimacoes.filter((i) => i.processo_id === processo.id)}
            prazos={prazos.filter((p) => p.processo_id === processo.id)}
            peticoes={peticoes.filter((p) => p.processo_id === processo.id)}
            busy={busy}
            offline={offline}
            onSelect={onSelect}
            onOpenPeticao={onOpenPeticao}
            onEditPrazo={onEditPrazo}
          />
        ) : null}

        {intimacao ? (
          <IntimacaoDetail
            intimacao={intimacao}
            processo={processos.find((p) => p.id === intimacao.processo_id) ?? null}
            prazo={prazos.find((p) => p.intimacao_id === intimacao.id) ?? null}
            offline={offline}
            onSelect={onSelect}
            onPrepareWork={onPrepareWork}
            onPrazoConfirmed={onPrazoConfirmed}
          />
        ) : null}

        {!processo && !intimacao ? (
          <div className="empty">
            <span>Registro não encontrado nos dados carregados.</span>
          </div>
        ) : null}
      </aside>
    </div>
  );
}

function ProcessoDetail({
  processo,
  intimacoes,
  prazos,
  peticoes,
  busy,
  offline,
  onSelect,
  onOpenPeticao,
  onEditPrazo
}: {
  processo: Processo;
  intimacoes: Intimacao[];
  prazos: Prazo[];
  peticoes: Peticao[];
  busy: string | null;
  offline: boolean;
  onSelect: (sel: DetailSelection) => void;
  onOpenPeticao: (peticao: Peticao) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
    <div className="detailBody">
      <h2 className="detailTitle">{processo.numero}</h2>
      <p className="detailSub">{processo.classe ?? "Classe não informada"}</p>

      <div className="detailMetaGrid">
        <DetailField label="Tribunal" value={processo.tribunal} />
        <DetailField label="Sistema" value={processo.sistema} />
        <DetailField label="Órgão julgador" value={processo.orgao_julgador} />
      </div>

      <DetailSection title="Prazos" count={prazos.length}>
        {prazos.length ? (
          prazos
            .slice()
            .sort((a, b) => a.data_fatal.localeCompare(b.data_fatal))
            .map((prazo) => (
              <div className="detailRow" key={prazo.id}>
                <div>
                  <strong>{prazo.descricao ?? "Prazo"}</strong>
                  <span>
                    {formatDate(prazo.data_fatal)} · {prazo.dias}{" "}
                    {prazo.dias_uteis ? "dias úteis" : "dias corridos"}
                    {prazo.cumprido ? " · cumprido" : ""}
                  </span>
                </div>
                <button
                  className="iconButton"
                  title="Revisar prazo"
                  disabled={offline || busy === `edit-${prazo.id}`}
                  onClick={() => onEditPrazo(prazo)}
                >
                  <CalendarDays size={15} />
                </button>
              </div>
            ))
        ) : (
          <p className="detailEmpty">Sem prazos vinculados.</p>
        )}
      </DetailSection>

      <DetailSection title="Intimações" count={intimacoes.length}>
        {intimacoes.length ? (
          intimacoes.map((intimacao) => (
            <button
              className="detailRow clickable"
              key={intimacao.id}
              onClick={() => onSelect({ kind: "intimacao", id: intimacao.id })}
            >
              <div>
                <strong>{intimacao.tipo_comunicacao ?? "Comunicação"}</strong>
                <span>{formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}</span>
              </div>
            </button>
          ))
        ) : (
          <p className="detailEmpty">Sem intimações capturadas.</p>
        )}
      </DetailSection>

      <DetailSection title="Minutas" count={peticoes.length}>
        {peticoes.length ? (
          peticoes.map((peticao) => (
            <button className="detailRow clickable" key={peticao.id} onClick={() => onOpenPeticao(peticao)}>
              <div>
                <strong>{peticao.tipo ?? "Petição"}</strong>
                <span>{statusLabel(peticao.status)}</span>
              </div>
              <FilePenLine size={15} />
            </button>
          ))
        ) : (
          <p className="detailEmpty">Nenhuma minuta gerada.</p>
        )}
      </DetailSection>
    </div>
  );
}

function IntimacaoDetail({
  intimacao,
  processo,
  prazo,
  offline,
  onSelect,
  onPrepareWork,
  onPrazoConfirmed
}: {
  intimacao: Intimacao;
  processo: Processo | null;
  prazo: Prazo | null;
  offline: boolean;
  onSelect: (sel: DetailSelection) => void;
  onPrepareWork: (intimacaoId: number, processoId: number | null, prazoId: number | null) => void;
  onPrazoConfirmed?: (prazo: Prazo) => void;
}) {
  return (
    <div className="detailBody">
      <h2 className="detailTitle">{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</h2>
      <p className="detailSub">
        {intimacao.numero_processo ?? processo?.numero ?? "Processo não identificado"}
      </p>

      <div className="detailMetaGrid">
        <DetailField label="Tribunal" value={intimacao.tribunal} />
        <DetailField label="Disponibilização" value={formatDate(intimacao.data_disponibilizacao)} />
        <DetailField label="Publicação" value={formatDate(intimacao.data_publicacao)} />
        <DetailField label="Fonte" value={intimacao.fonte} />
      </div>

      {prazo ? (
        <div className="detailCallout">
          <CalendarDays size={15} />
          <span>
            Prazo: <strong>{formatDate(prazo.data_fatal)}</strong> ({prazo.dias}{" "}
            {prazo.dias_uteis ? "dias úteis" : "dias corridos"})
            {prazo.revisao_status !== "confirmado" ? " · calculado a revisar" : " · confirmado"}
          </span>
        </div>
      ) : null}

      {intimacao.prazo_analise ? <p role="status" className="officeHint">Análise: {intimacao.prazo_analise.status}. {intimacao.prazo_analise.motivo}</p> : null}
      {!offline && (!prazo || prazo.revisao_status !== "confirmado") && <ConfirmarPrazo key={intimacao.id} intimacaoId={intimacao.id} analise={intimacao.prazo_analise} onConfirmed={onPrazoConfirmed} />}
      <DetailSection title="Teor da intimação">
        <TeorHtml teor={intimacao.teor} />
      </DetailSection>

      <div className="detailActions">
        <button
          className="toolbarButton primary"
          disabled={offline}
          onClick={() => onPrepareWork(intimacao.id, processo?.id ?? intimacao.processo_id, prazo?.id ?? null)}
        >
          Preparar minuta
        </button>
        {processo ? (
          <button
            className="toolbarButton"
            onClick={() => onSelect({ kind: "processo", id: processo.id })}
          >
            Ver processo
          </button>
        ) : <p role="status" className="officeHint">Processo não vinculado. Confira a identificação desta intimação antes de preparar a minuta.</p>}
      </div>
    </div>
  );
}

function DetailSection({
  title,
  count,
  children
}: {
  title: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <section className="detailSection">
      <header>
        <strong>{title}</strong>
        {count !== undefined ? <span>{count}</span> : null}
      </header>
      <div className="detailSectionBody">{children}</div>
    </section>
  );
}

function DetailField({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="detailField">
      <span>{label}</span>
      <strong>{value ?? "-"}</strong>
    </div>
  );
}

/** Renderiza o teor da intimação: HTML sanitizado (se houver tags) ou texto puro. */
function TeorHtml({ teor }: { teor: string | null | undefined }) {
  const html = useMemo(() => (teor ? sanitizeHtml(teor) : ""), [teor]);
  if (!teor) {
    return <p className="detailTeor">Teor não informado.</p>;
  }
  const looksLikeHtml = /<[a-zA-Z!/][^>]*>/.test(teor);
  if (looksLikeHtml) {
    return <div className="detailTeor" dangerouslySetInnerHTML={{ __html: html }} />;
  }
  return <p className="detailTeor">{teor}</p>;
}
