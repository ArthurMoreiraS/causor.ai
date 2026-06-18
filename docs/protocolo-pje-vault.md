# Protocolo PJe assistido + vault

## Decisao

O Causor nao guarda senha do PJe. O advogado autentica no PJe em uma sessao
assistida; o sistema guarda apenas o estado de sessao/cookies ou token de
provedor em vault criptografado.

Em producao, configure:

```env
CAUSOR_VAULT_PROVIDER=supabase
```

e habilite a extensao Supabase Vault no projeto. O backend chama
`vault.create_secret(...)` e grava no SOR apenas uma referencia
`supabase-vault://...`.

Em desenvolvimento, `CAUSOR_VAULT_PROVIDER=localdev` cria somente uma
referencia deterministica `localdev://...` sem persistir o segredo bruto.

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

No Causor, o fluxo funcional fica assim:

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
4. Ao chamar `POST /peticoes/{id}/protocolar/async` com essa `credencial_id`, o
   backend renderiza a minuta em PDF, reabre a sessao PJe, pesquisa o processo,
   entra nos autos e acessa a area de `Anexar Peticoes/Documentos` ou
   `Peticionar`.
5. O conector anexa o PDF e para em `ready_to_sign`.
6. O advogado assina/envia no PJe/PJeOffice.
7. O protocolo final e registrado no Causor via
   `POST /peticoes/{id}/protocolar/confirmar`.

O conector nao possui metodo para clicar em `Assinar documento`, `Protocolar`,
`Protocolar em lote` ou equivalentes.

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

## Assinatura

Modo inicial: `manual_pjeoffice`.

1. Playwright prepara o protocolo.
2. O fluxo para em `ready_to_sign`.
3. O advogado assina/envia no PJe/PJeOffice.
4. O Causor registra o protocolo por confirmacao manual.

Modo futuro: `cloud_certificate`.

1. Credencial do provedor ICP-Brasil em nuvem fica no Supabase Vault.
2. O conector PJe chama o provedor de assinatura.
3. O advogado confirma via push/OTP quando exigido.
4. O Causor conclui o envio e registra comprovante automaticamente.

Fallback A1 cifrado deve ser usado apenas se o provedor em nuvem nao atender o
piloto; A3/token fisico fica fora do escopo de automacao de servidor.
