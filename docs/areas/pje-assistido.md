# Protocolo PJe assistido + vault

Decisão, fluxo, assinatura e como testar o conector PJe do Causor.

## Decisão

O Causor não guarda senha do PJe. O advogado autentica no PJe em uma sessão
assistida; o sistema guarda apenas o estado de sessão/cookies ou token de
provedor em vault criptografado.

Em produção, configure:

```env
CAUSOR_VAULT_PROVIDER=supabase
```

e habilite a extensão Supabase Vault no projeto. O backend chama
`vault.create_secret(...)` e grava no SOR apenas uma referencia
`supabase-vault://...`.

Em desenvolvimento, `CAUSOR_VAULT_PROVIDER=localdev` cria somente uma
referencia deterministica `localdev://...` sem persistir o segredo bruto.

## Estado atual do software

- Claude-only:
  - chat: `claude-haiku-4-5`;
  - classificacao: `claude-haiku-4-5`;
  - minuta: `claude-sonnet-4-6`.
- Gemini removido do codigo e das docs.
- Fluxo de protocolo PJe existe como base assistida:
  - `POST /peticoes/{id}/protocolar/async` para processo `PJe` cria job e para em
    `ready_to_sign`;
  - nao marca a peticao como `protocolada` automaticamente;
  - `POST /peticoes/{id}/protocolar/confirmar` registra o numero final do
    protocolo depois do envio real.
- Vault:
  - `CAUSOR_VAULT_PROVIDER=localdev` em desenvolvimento;
  - `CAUSOR_VAULT_PROVIDER=supabase` para gravar sessoes/tokens no Supabase Vault;
  - nunca guardar senha do PJe, certificado, `.pfx`, chave privada ou OTP no SOR.

## Endpoints

- `POST /usuarios/{usuario_id}/pje-sessoes`
  - Cadastra uma sessao PJe assistida como `CredencialAssinatura` de provedor
    `PJeSession`.
  - Aceita `storage_state` Playwright, mas rejeita campos com nome de senha,
    certificado, `.pfx` ou chave privada.

- `POST /peticoes/{peticao_id}/protocolar/async`
  - Se o processo for `PJe`, prepara o protocolo assistido e para em
    `ready_to_sign`.
  - Se o processo ainda nao tiver conector real, preserva o fake local atual.

- `POST /peticoes/{peticao_id}/protocolar/confirmar`
  - Depois que o advogado assina/envia no PJe/PJeOffice, registra o numero do
    protocolo e marca a peticao como `protocolada`.

## Fluxo operacional alinhado ao PJe

O PJe exige ambiente do advogado configurado para acesso e assinatura. Para
advogados, o acesso com certificado digital e o assinador/PJeOffice sao o caminho
que permite assinar documentos e protocolar; acesso sem certificado tem
restricoes e nao deve ser tratado como caminho principal do produto.

1. O operador roda, em ambiente local/treino, o comando:

   ```bash
   python -m app.cli pje-capture-session \
     --usuario 1 \
     --tribunal TJSP \
     --url-base https://pje-treinamento.tjsp.jus.br/pje
   ```

2. O Playwright abre o PJe. O advogado faz login diretamente no PJe, usando o
   mecanismo do proprio tribunal (certificado digital/gov.br, conforme o
   ambiente).
3. O Causor salva apenas o `storage_state` Playwright no vault como credencial
   `PJeSession`.
4. Advogado gera e revisa a minuta no Causor.
5. Advogado aprova no Gate OAB.
6. Advogado clica em `Preparar protocolo PJe` (`POST /peticoes/{id}/protocolar/async`
   com a `credencial_id`). O backend renderiza a minuta em PDF, reabre a sessao
   PJe, pesquisa o processo, entra nos autos e acessa a area de
   `Anexar Peticoes/Documentos` ou `Peticionar`.
7. O conector seleciona o tipo de peticao e anexa o PDF/minuta/documentos.
8. O fluxo para em `ready_to_sign`.
9. O advogado assina/envia no PJe/PJeOffice.
10. O advogado registra o numero do protocolo no Causor via
    `POST /peticoes/{id}/protocolar/confirmar`.
11. O Causor marca a peticao como `protocolada` e registra auditoria.

O conector nao possui metodo para clicar em `Assinar documento`, `Protocolar`,
`Protocolar em lote` ou equivalentes.

## Tela desejada

Criar tela/modal `Protocolo PJe` com timeline:

- Login no PJe
- Processo localizado
- Peticionamento aberto
- Minuta anexada
- Pronto para assinatura (`ready_to_sign`)
- Protocolo confirmado

Estados por etapa:

- `pendente`
- `executando`
- `concluido`
- `bloqueado`
- `precisa_do_advogado`

Botoes:

- `Abrir sessao PJe`
- `Continuar automacao`
- `Assumir manualmente`
- `Registrar protocolo final`
- `Ver auditoria`
- `Cancelar job`

## Assinatura

A forma de assinar vem do provedor da credencial via o seam
`app/signing/providers.py` (`SignatureProvider`). A coluna
`credencial_assinatura.modo` define o caminho.

Modo inicial: `manual_handoff` (BirdID/VIDaaS/PJeOffice/A3/A1).

1. Playwright prepara o protocolo.
2. O fluxo para em `ready_to_sign`.
3. O conector produz um `SignatureHandoff` (mensagem + instrucoes por provedor),
   sem segredo, e o job o anexa ao resultado/auditoria.
4. O advogado assina/envia fora do Causor (no app do provedor / PJe / PJeOffice).
5. O Causor registra o protocolo por confirmacao manual; a auditoria grava o
   provedor/modo da credencial usada.

Modo futuro: `api` (assinatura em nuvem). O gancho ja existe em
`SignatureProvider.request_signature()` (hoje levanta `NotImplementedError`):

1. Token/credencial do provedor ICP-Brasil em nuvem fica no Supabase Vault
   (nunca PIN/senha).
2. O provedor e chamado via API; o advogado confirma via push/OTP quando exigido.
3. O Causor conclui o envio e registra comprovante automaticamente.

Fallback A1 cifrado so se o provedor em nuvem nao atender o piloto; A3/token
fisico fica fora do escopo de automacao de servidor.

## Como testar sem acesso ao PJe real

Sem advogado, certificado ou ambiente de homologacao, o caminho correto e testar
em tres camadas:

1. Testes unitarios com fakes: validam PDF, vault, job, auditoria e a maquina de
   estados do conector.
2. Simulador local de PJe: valida Playwright real, upload de PDF, seletores e
   checkpoint `ready_to_sign` sem acessar tribunal.
3. Teste live opt-in futuro: quando houver URL de treino e processo descartavel,
   rodar contra homologacao.

Para subir o simulador local:

```bash
python -m app.cli pje-simulator --port 8765
```

O endereco para testar e:

```text
http://127.0.0.1:8765
```

Para rodar o teste Playwright ponta a ponta contra o simulador:

```bash
RUN_PJE_SIMULATOR=1 python -m pytest tests/test_pje_simulator_integration.py -q
```

No PowerShell:

```powershell
$env:RUN_PJE_SIMULATOR='1'
python -m pytest tests/test_pje_simulator_integration.py -q
```

Esse teste nao prova compatibilidade com um tribunal especifico; ele prova que o
nosso software executa o fluxo de navegador esperado ate o gate seguro.

## O que nao fazer

- Nao guardar login/senha do PJe no Causor.
- Nao guardar certificado, `.pfx`, chave privada ou OTP.
- Nao burlar captcha.
- Nao assinar nem protocolar sem gate humano.
- Nao implementar varios tribunais ao mesmo tempo.

## Primeiro MVP real sugerido

Alvo: peticao intermediaria em processo PJe existente.

Fora do primeiro fluxo:

- peticao inicial;
- custas;
- multiplos anexos complexos;
- segredo de justica;
- multiplos tribunais;
- captcha automatizado;
- assinatura cloud.

## Informacoes necessarias quando retomar

- URL do PJe usado.
- 1o grau ou 2o grau.
- Processo real ou homologacao seguro para teste.
- Tipo de peticao intermediaria do primeiro fluxo.
- Confirmar se PJeOffice funciona na maquina do advogado.
