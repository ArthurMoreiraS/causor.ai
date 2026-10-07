# Reformulação da interface "Papel e tinta" — 07/10/2026

## Objetivo e limites

Unificar a interface em um único sistema visual, meio-termo aprovado pelo
fundador entre a identidade atual do software e a da landing:

- Da landing: Satoshi nos títulos, fundo papel `#f9f8f5`, tinta `#20231f`,
  verde `#425b47` como único acento, foco azul.
- Do software: Inter na interface, painéis brancos, bordas finas, cantos
  4/6/8, botão principal sólido, densidade de tabela, mono só no número CNJ.

Sem mudança de comportamento, endpoints ou regras de prazo. Só `frontend/`.

## Causas encontradas

1. Só Inter 400/700 era carregada; o CSS pedia 500/600/650 e o navegador
   arredondava. JetBrains Mono nunca foi carregada (caía para Consolas).
2. 30 tamanhos de fonte e 13 espaçamentos entre letras diferentes.
3. Dois sistemas de estilo (`globals.css` e `office.css`), com cabeçalhos de
   página diferentes por módulo.
4. Tabelas com cabeçalho e linhas em grades separadas e colunas fixas menores
   que os selos.

## Execução

1. Fundação: fontes auto-hospedadas (Inter variável, Satoshi, JetBrains Mono),
   tokens de cor e escala 12/13/14/16/20/28 com pesos 400/500/600.
2. Normalização do CSS: tamanhos, pesos e cores pelos tokens; sem caixa alta
   em mono; remoção de regras sem uso (agente local, protocolo, conectores).
3. Componentes: `PageHeader`, selos (uma família, frase normal), tabela com
   `subgrid` (cabeçalho e linhas na mesma grade), botões que não quebram.
4. Telas na ordem do fluxo: shell e sidebar, Intimações, Prazos, Processos e
   autos, Trabalhos, Minutas e Revisão, Clientes, Tarefas, Documentos,
   Modelos, Histórico, Configuração, Assistente, Login.
5. Correções junto: número CNJ formatado, nomes de sistema (PJe, eproc,
   e-STJ), entidades HTML decodificadas no teor.
6. Teste de guarda: falha se surgir tamanho, peso, família ou caixa alta fora
   dos tokens.

## Aceite e verificação

- `pnpm check` e `pnpm build` verdes.
- Prints de antes e depois das telas principais nos temas claro e escuro,
  com o app local contra API simulada de dados fictícios (sem tocar no
  Supabase de produção).
- Evidência é **local**; implantação só quando o fundador pedir o push.
