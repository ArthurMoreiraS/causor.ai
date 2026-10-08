"use client";

import { useEffect, useState } from "react";
import { carregarUsuarioAtual, type CurrentUser, type Papel, type Permissao } from "./api";

// A matriz vive no backend (app/auth/papeis.py) e chega pronta em /me. Aqui só
// se decide o que mostrar: quem bloqueia de verdade é a API (403).

export const PAPEIS: Papel[] = ["administrador", "advogado", "assistente"];

export const PAPEL_LABEL: Record<Papel, string> = {
  administrador: "Administrador",
  advogado: "Advogado",
  assistente: "Assistente"
};

export const PAPEL_DESCRICAO: Record<Papel, string> = {
  administrador: "Faz todo o fluxo e cuida da equipe, das OABs e da configuração do escritório.",
  advogado: "Faz todo o fluxo, decide prazos e aprova minutas.",
  assistente: "Cuida de tarefas, documentos e rascunhos. Não aprova minuta nem altera prazo."
};

/**
 * Enquanto `/me` não respondeu, `pode` devolve `true`: o caso comum (sócio e
 * advogado) não vê botões piscando, e a API recusa o que não for permitido.
 */
export function usePermissoes(enabled = true) {
  const [me, setMe] = useState<CurrentUser | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    carregarUsuarioAtual()
      .then((user) => { if (active) setMe(user); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [enabled]);
  return {
    me,
    pode: (permissao: Permissao) => (me ? me.permissoes.includes(permissao) : true)
  };
}
