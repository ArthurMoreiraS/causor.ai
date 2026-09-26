"use client";
import { useEffect, useState } from "react";
import { request, type Pagina } from "@/lib/api";
import type { DestinoPacote, Tentativa } from "@/lib/package-api";
import { humanError } from "@/lib/errors";

type Entry = Tentativa & { trabalho_id: number | null; providencia: string; destino: DestinoPacote; versao_pacote: number };
const labels: Record<string, string> = { aguardando_envio_externo: "Aguardando envio externo", envio_informado: "Envio informado; aguarda conferência", envio_confirmado: "Comprovante conferido pelo advogado", resultado_incerto: "Resultado incerto; não repetir envio", cancelado: "Cancelado antes do envio" };
export default function AssistedHistory({ refreshKey, offline }: { refreshKey: number; offline: boolean }) {
  const [items, setItems] = useState<Entry[]>([]), [total, setTotal] = useState(0), [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    if (offline) return;
    request<Pagina<Entry>>(`/envios-assistidos?limit=30&offset=${offset}`).then(result => {
      if (active) { setItems(result.items); setTotal(result.total); setError(null); }
    }).catch(err => { if (active) setError(humanError(err, "Falha ao consultar envios assistidos")); });
    return () => { active = false; };
  }, [refreshKey, offline, offset]);
  return <section className="legalWorkStage"><h2>Envios acompanhados por trabalho</h2>
    <p>Exportação, declaração de envio e conferência de comprovante são etapas distintas.</p>
    {error ? <p role="alert">{error}</p> : null}
    {items.map(item => <article className="legalEvidenceQuote" key={item.id}><h3>{item.providencia}</h3>
      <p>{item.destino.numero_processo} · {item.destino.grau}º grau · Pacote v{item.versao_pacote}</p>
      <p>{labels[item.status] || item.status}</p>
      {item.trabalho_id ? <a className="toolbarButton compact" href={`/?trabalho=${item.trabalho_id}#trabalhos`}>Abrir trabalho e comprovante</a> : null}
    </article>)}
    {!items.length && !error ? <p>Nenhuma tentativa de envio assistido registrada.</p> : null}
    {total > 30 ? <div className="tablePager"><button disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 30))}>Anterior</button><span>{total} envios</span><button disabled={offset + 30 >= total} onClick={() => setOffset(v => v + 30)}>Próximos</button></div> : null}
  </section>;
}
