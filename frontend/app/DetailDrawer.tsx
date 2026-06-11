"use client";

import { CalendarDays, FilePenLine, Loader2, Sparkles, X } from "lucide-react";
import type { ReactNode } from "react";
import type { Intimacao, Peticao, Prazo, Processo } from "@/lib/api";

export type DetailSelection =
  | { kind: "processo"; id: number }
  | { kind: "intimacao"; id: number };

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

function statusLabel(status: string) {
  if (status === "rascunho") return "Em revisão";
  if (status === "aprovada") return "Aprovada";
  if (status === "protocolada") return "Protocolada";
  return status;
}

export default function DetailDrawer({
  selection,
  processos,
  intimacoes,
  prazos,
  peticoes,
  busy,
  offline,
  onClose,
  onSelect,
  onGenerateDraft,
  onOpenPeticao,
  onEditPrazo
}: {
  selection: DetailSelection;
  processos: Processo[];
  intimacoes: Intimacao[];
  prazos: Prazo[];
  peticoes: Peticao[];
  busy: string | null;
  offline: boolean;
  onClose: () => void;
  onSelect: (sel: DetailSelection) => void;
  onGenerateDraft: (intimacaoId: number) => void;
  onOpenPeticao: (peticao: Peticao) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  const processo =
    selection.kind === "processo" ? processos.find((p) => p.id === selection.id) ?? null : null;
  const intimacao =
    selection.kind === "intimacao" ? intimacoes.find((i) => i.id === selection.id) ?? null : null;

  return (
    <div className="drawerOverlay" onClick={onClose}>
      <aside className="detailDrawer" onClick={(e) => e.stopPropagation()}>
        <header className="detailDrawerHead">
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
            busy={busy}
            offline={offline}
            onSelect={onSelect}
            onGenerateDraft={onGenerateDraft}
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
  busy,
  offline,
  onSelect,
  onGenerateDraft
}: {
  intimacao: Intimacao;
  processo: Processo | null;
  prazo: Prazo | null;
  busy: string | null;
  offline: boolean;
  onSelect: (sel: DetailSelection) => void;
  onGenerateDraft: (intimacaoId: number) => void;
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
          </span>
        </div>
      ) : null}

      <DetailSection title="Teor da intimação">
        <p className="detailTeor">{intimacao.teor ?? "Teor não informado."}</p>
      </DetailSection>

      <div className="detailActions">
        <button
          className="toolbarButton primary"
          disabled={offline || busy === `draft-${intimacao.id}`}
          onClick={() => onGenerateDraft(intimacao.id)}
        >
          {busy === `draft-${intimacao.id}` ? (
            <Loader2 className="spin" size={15} />
          ) : (
            <Sparkles size={15} />
          )}
          Gerar minuta
        </button>
        {processo ? (
          <button
            className="toolbarButton"
            onClick={() => onSelect({ kind: "processo", id: processo.id })}
          >
            Ver processo
          </button>
        ) : null}
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
