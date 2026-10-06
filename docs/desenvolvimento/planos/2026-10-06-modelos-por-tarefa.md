# Modelos por tarefa — 06/10/2026

Fundador autorizou corrigir a distribuição recomendada e fazer push na main.

## Escopo e aceite

- Sonnet 5.5 para análise de evidências/minutas; Haiku 4.5 continua no chat,
  classificação/interpretação de comandos e resumo documental padrão.
- Upload permite resumo aprofundado com Sonnet, escolha persistida no job e
  conservada em tentativas. Sem sobrescrever resumos completos já utilizados.
- Configuração local/exemplos e deploy alinhados, preservando outros settings,
  segredos e escolhas de modelos personalizados. Log somente de modelos.
- Avaliação existente admite comparar Sonnet 5/5.5 com entradas iguais e
  registrar consumo/latência. Sem afirmar ganho jurídico com testes simulados.
- Testes de roteamento, payload/API, retries, citações e cliente frontend;
  conferir diff, CI e deploy após push. Prazo determinístico e revisão mantidos.

## Fontes verificadas

Catálogo da conta confirmou Haiku 4.5, Sonnet 5 e Sonnet 5.5 disponíveis.
[Migração oficial](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide):
adaptive thinking compatível, sem sampling/prefill/forced tool choice.
[Preços](https://platform.claude.com/docs/en/about-claude/pricing): Sonnet 5/5.5
têm a mesma tarifa básica; quantidade de tokens/latência precisam ser medidas.
Não há caso autorizado para comparação jurídica real; preparar o instrumento
e validar compatibilidade técnica com dados sintéticos limitados.

## Verificação realizada

- Regressões novas falharam antes da implementação: perfil não aceito, não
  persistido e seleção arbitrária de modelo não bloqueada. Depois: 61 testes
  direcionados aprovados e Ruff. Frontend: lint/tipos e 163 testes aprovados;
  build aprovado. Nenhum fixture jurídico real usado.
- Comparação real com um caso fictício e entrada idêntica: Sonnet 5 e 5.5
  completaram o schema nativo. Latência 23,1s/17,0s; saída 1.707/2.157 tokens.
  Terceira chamada: resumo aprofundado 5.5 com citações literais validadas.
  Isso comprova compatibilidade; não mede precisão jurídica ou custo típico.
- Suíte completa detectou contrato antigo em `test_minuta_usa_sonnet_por_padrao`
  esperando Sonnet 5. Atualizado para 5.5; suíte repetida antes do push.
- Configuração local atualizada com backup privado ignorado. Deploy aplica
  atualização seletiva e mostra somente nomes conhecidos de modelos.
- Suíte completa após corrigir o contrato: 843 aprovados/112 ignorados, 12
  avisos exclusivamente de HMAC curto dos fixtures. SQLite descartável e
  credenciais externas vazias; Ruff completo aprovado. Diff revisado e check
  aprovado.

## Main e produção

- Código enviado à main no commit `0fa24e2cce9d4dffacc900462f23aa54f481ec51`.
  [CI aprovado](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37538041609):
  843 backend/112 ignorados, 163 frontend e 104 PostgreSQL em cada versão
  16/17, Ruff, lint/tipos e build Linux aprovados.
- [Deploy aprovado](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37538261729):
  SHA conferido em backend, worker, autos-worker, capture-scheduler e frontend.
  Atualização seletiva alterou somente os dois settings Sonnet legados.
  Log efetivo confirmou draft `claude-sonnet-5-5` e context/classification/chat
  `claude-haiku-4-5`; credenciais não foram exibidas.
- Verificação externa após deploy: health/login 200, Auth técnica sem enviar
  email, usuário/escritório original preservados e oito rotas autenticadas 200.
  Upload com perfil inválido retornou 422 no campo `perfil_resumo`, sem arquivos
  nem chamadas LLM. Sem sessão: 401; REST direto ao SOR: 403. Frontend contém
  configuração pública do novo Supabase Free e nenhuma chave administrativa.
  Sessão técnica encerrada sem afetar outras sessões.
- APIs LLM reais foram verificadas com dados fictícios localmente; não se
  executou um caso jurídico real em produção. Revisão da utilidade/correção
  jurídica da minuta pelo advisor permanece pendente.
