"use client";

import { CheckCircle2, CircleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AcessoCapacidade, AcessoTribunal, listarAcessoTribunais } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { AsyncState, Skeleton } from "./ui";

// O painel é organizado por **capacidade**, não por tecnologia: o advogado
// precisa saber, por tribunal, se consegue redigir e se consegue protocolar —
// nunca qual canal atende. Duas consequências deliberadas:
//
// - "pelo seu computador" aparece em toda linha de Protocolar, em todo
//   tribunal, porque protocolar depende sempre da máquina pareada (o canal
//   oficial cobre só leitura).
// - Nenhum texto visível usa jargão ("MNI", "agente"); o teste do componente
//   trava isso.
//
// Diagnóstico, não ação: os botões de conectar vivem no assistente JIT, que já
// aparece dentro do fluxo da minuta. Aqui se responde "estou pronto?" fora do
// calor do momento.

function rotulo(cap: AcessoCapacidade): { pronto: boolean; texto: string } {
  if (cap.disponivel) {
    return {
      pronto: true,
      texto: cap.via === "oficial" ? "direto do tribunal" : "pelo seu computador"
    };
  }
  if (cap.falta === "reconectar") {
    return { pronto: false, texto: "a sessão expirou — entre no tribunal de novo" };
  }
  if (cap.falta === "integracao_indisponivel") {
    return { pronto: false, texto: "automação ainda indisponível para este tribunal" };
  }
  if (cap.falta === "parear") {
    return { pronto: false, texto: "pareie o seu computador abaixo" };
  }
  return { pronto: false, texto: "entre no tribunal uma vez" };
}

function Linha({ nome, capacidade }: { nome: string; capacidade: AcessoCapacidade }) {
  const { pronto, texto } = rotulo(capacidade);
  return (
    <div className={pronto ? "acessoLinha ok" : "acessoLinha pendente"}>
      {pronto ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
      <span className="acessoCapacidade">{nome}</span>
      <span className="acessoEstado">{texto}</span>
    </div>
  );
}

export function rotaPronta(rota: AcessoTribunal): boolean {
  return rota.ler_autos.disponivel && rota.protocolar.disponivel;
}

export default function AcessoTribunaisPanel({ offline }: { offline: boolean }) {
  const [rotas, setRotas] = useState<AcessoTribunal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const reload = useCallback(async () => {
    try {
      setRotas(await listarAcessoTribunais());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Falha ao carregar os tribunais do escritório"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (offline) {
      setLoading(false);
      return;
    }
    void reload();
  }, [offline, reload]);

  const prontos = rotas.filter(rotaPronta).length;

  return (
    <div className="settingsGroup">
      <div className="acessoPainelHead">
        <span className="settingsLabel">Seus tribunais</span>
        {rotas.length > 0 && (
          <small className="acessoResumo">
            {prontos} de {rotas.length} prontos
          </small>
        )}
      </div>

      <AsyncState
        loading={loading}
        error={error}
        empty={!rotas.length}
        skeleton={
          <>
            <Skeleton height={72} radius={8} />
            <Skeleton height={72} radius={8} />
          </>
        }
        emptyState={
          <small className="settingsHint">
            Nenhum tribunal ainda. Assim que o Causor capturar o primeiro processo, ele
            aparece aqui com o que já dá para fazer.
          </small>
        }
        retrying={retrying}
        onRetry={() => {
          setRetrying(true);
          void reload().finally(() => setRetrying(false));
        }}
      >
        {rotas.map((rota) => (
          <article
            className="acessoRota"
            key={`${rota.sistema}-${rota.tribunal}-${rota.grau}`}
          >
            <header>
              <strong>
                {rota.tribunal} · {rota.grau}º grau
              </strong>
              <span className="acessoProcessos">
                {rota.processos} {rota.processos === 1 ? "processo" : "processos"}
              </span>
            </header>
            <Linha nome="Ler os autos" capacidade={rota.ler_autos} />
            <Linha nome="Protocolar" capacidade={rota.protocolar} />
          </article>
        ))}
      </AsyncState>
    </div>
  );
}
