# Protocolo assistido + assinatura

Como o Causor protocola hoje, onde o fluxo para e como testar sem acesso a
tribunal real.

> **Revisado em 2026-07-22.** Este arquivo documentava três caminhos que já
> não existem no código (`POST /usuarios/{id}/pje-sessoes`, o CLI
> `pje-capture-session` e o CLI `pje-simulator`), além de uma "tela desejada"
> que nunca foi construída. Foram removidos. Se precisar do histórico dessas
> decisões, veja `docs/historico/superpowers/`.

## Onde o protocolo se encaixa

O Causor tem **duas fontes de acesso ao tribunal** e um só roteador
(`resolve_capture_fonte`): o canal oficial **MNI** e o **agente local** na
máquina do advogado. Para *leitura* dos autos, as duas servem. Para
*protocolo*, **hoje só o agente local** — o `MniFilingDriver`
(`entregarManifestacaoProcessual`) ainda não existe, embora a fundação esteja
pronta.

Escada do protocolo, da melhor opção ao fallback (sempre com o Gate OAB na
frente):

1. **MNI `entregar`** — oficial, no servidor, comprovante na resposta.
   *A construir; ver [`mni-credenciamento.md`](mni-credenciamento.md).*
2. **Agente local até `ready_to_sign`** — construído; os drivers reais dos
   tribunais são as Tasks 6–9 do Plano 3, repriorizadas.
3. **Confirmação manual** — funciona hoje.

**O backend hospedado nunca abre Playwright.** Em modo real, o despacho vai
para o agente (`queue/jobs.py`); o caminho in-backend foi fechado em `194f180`.

## Custódia de credenciais

A restrição de que sessão/senha/certificado só podiam viver no vault do Causor
ou na máquina do advogado **foi removida** — ver `AGENTS.md`, restrição não
negociável #1, que é a fonte dessa regra. O que permanece intocável: **segredo
nunca entra em log nem em prompt de LLM**, esteja onde estiver.

Configuração do vault (`CAUSOR_VAULT_PROVIDER`) está em
[`../operacao/deploy.md`](../operacao/deploy.md); não é repetida aqui.

## Endpoints

- `POST /peticoes/{peticao_id}/protocolar/async`
  - Prepara o protocolo e para em `ready_to_sign`. Não marca a petição como
    `protocolada`.
  - Em modo real, enfileira `prepare_filing` para o agente local.
- `POST /peticoes/{peticao_id}/protocolar/confirmar`
  - Depois que o advogado assina/envia, registra o número do protocolo e marca
    a petição como `protocolada`.

Protocolo sem número e comprovante verificados **nunca** marca
`Peticao.status="protocolada"`.

## Fluxo operacional

O PJe exige o ambiente do advogado configurado para acesso e assinatura. O
acesso com certificado digital + PJeOffice é o caminho que permite assinar e
protocolar; acesso sem certificado tem restrições e não é o caminho principal.

1. O advogado pareia o computador (Configurações → Acesso aos tribunais) e faz
   login no portal quando o assistente pedir. A sessão vive **só** no perfil
   Playwright persistente do agente — nenhum cookie ou token chega ao backend.
2. Os autos são capturados (por MNI ou pelo agente, conforme a rota) e o
   contexto precisa ficar `ready`.
3. O advogado gera e revisa a minuta.
4. Aprova no Gate OAB.
5. Dispara `protocolar/async`: o backend renderiza o PDF e envia o comando ao
   agente, que reusa a sessão, localiza o processo e abre o peticionamento.
6. O fluxo para em `ready_to_sign`. O conector **não** tem método para clicar
   em `Assinar`, `Protocolar` ou equivalentes.
7. O advogado assina/envia no PJe/PJeOffice.
8. Registra o número via `protocolar/confirmar`; o Causor audita.

## Assinatura

A forma de assinar vem do provedor da credencial via o seam
`app/signing/providers.py` (`SignatureProvider`); a coluna
`credencial_assinatura.modo` define o caminho.

**Modo atual — `manual_handoff`** (BirdID/VIDaaS/PJeOffice/A3/A1): o conector
produz um `SignatureHandoff` (mensagem + instruções por provedor, sem segredo)
anexado ao resultado e à auditoria; o advogado assina fora do Causor e
confirma o protocolo depois.

**Modo futuro — `api`** (assinatura em nuvem): o gancho existe em
`SignatureProvider.request_signature()` e hoje levanta `NotImplementedError`.
Token do provedor ICP-Brasil em nuvem ficaria no Supabase Vault (nunca
PIN/senha), com confirmação por push/OTP.

Fallback A1 cifrado só se o provedor em nuvem não atender o piloto; A3/token
físico fica fora do escopo de automação de servidor.

> **Atalho possível:** o credenciamento MNI pode dispensar esta seção inteira.
> A Lei 11.419/2006 (art. 1º, §2º, III) reconhece o cadastro de usuário no
> Judiciário como assinatura eletrônica válida. A confirmar por tribunal — a
> pergunta está no checklist do ofício em
> [`mni-credenciamento.md`](mni-credenciamento.md).

## Como testar sem acesso a tribunal real

Três camadas, da mais barata à mais cara:

1. **Testes unitários com fakes** — validam PDF, vault, job, auditoria e a
   máquina de estados do conector. Rodam por padrão.
2. **Simuladores sanitizados** (`app/connectors/simulators/`: `pje`, `eproc`,
   `esaj`, `projudi`, `mni`) — servidores HTTP locais com páginas sintéticas.
   São levantados pelos próprios testes, não por um CLI:

   ```powershell
   cd backend
   $env:RUN_PJE_SIMULATOR='1'
   .\.venv\Scripts\python.exe -m pytest tests/test_pje_simulator_integration.py -q
   ```

   O simulador MNI roda sem variável de ambiente:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_mni_simulator_integration.py -q
   ```

3. **Testes live opt-in** — `RUN_MNI_LIVE=1` para o MNI (exige credencial de
   credenciamento); para os portais, exige URL de treino e processo
   descartável.

Simulador prova que **o nosso software** executa o fluxo esperado até o gate
seguro. Não prova compatibilidade com um tribunal específico — só o teste live
prova.

## O que não fazer

- Não gravar senha/certificado/`.pfx`/chave privada/OTP em log ou prompt de
  LLM, esteja a credencial no vault, no agente ou num vendor delegado.
- Não burlar captcha.
- Não assinar nem protocolar sem gate humano.
- Não implementar vários tribunais ao mesmo tempo.
- Não registrar endpoint MNI não confirmado (falha de MNI não cai para o
  agente — ver [`mni-credenciamento.md`](mni-credenciamento.md)).

## Primeiro fluxo real sugerido

Alvo: **petição intermediária em processo existente**.

Fora do primeiro fluxo: petição inicial, custas, múltiplos anexos complexos,
segredo de justiça, múltiplos tribunais, captcha automatizado, assinatura
cloud.

Informações necessárias quando retomar: tribunal e grau; se atende por MNI
(`resolve_mni_profile`); processo real ou de homologação seguro; tipo de
petição intermediária; e — se o caminho for o agente — se o PJeOffice funciona
na máquina do advogado.
