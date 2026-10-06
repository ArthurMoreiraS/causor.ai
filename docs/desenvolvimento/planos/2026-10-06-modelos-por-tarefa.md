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
  esperando Sonnet 5. Atualizado para 5.5; repetir suíte antes do push.
- Configuração local atualizada com backup privado ignorado. Deploy aplica
  atualização seletiva e mostra somente nomes conhecidos de modelos.
  CI/implantação desta mudança ainda pendentes.
- Suíte completa após corrigir o contrato: 843 aprovados/112 ignorados, 12
  avisos exclusivamente de HMAC curto dos fixtures. SQLite descartável e
  credenciais externas vazias; Ruff completo aprovado. Diff revisado e check
  aprovado. Testes PostgreSQL reais ficam para o CI descartável.
