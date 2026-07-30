# MNI — endpoints verificados e credenciamento

Este arquivo tem três partes: **(0)** a ressalva crítica de 2026-07-29 sobre
**quem** o MNI admite credenciar; **(1)** o resultado da varredura de endpoints
de 2026-07-22, base da tabela em `backend/app/connectors/mni/profiles.py`; e
**(2)** o material do ofício de credenciamento.

---

## 0. Ressalva crítica (2026-07-29): o MNI pode não admitir CNPJ privado

**Leia antes de enviar qualquer ofício.** A seção 2 deste arquivo foi escrita
sob a premissa de que o credenciamento é um trâmite burocrático gratuito. A
pesquisa de mercado de 2026-07-29
([`viabilidade-mercado-2026-07-29.md`](viabilidade-mercado-2026-07-29.md) §2)
encontrou quatro fontes convergentes indicando que o MNI é desenhado para
**órgão público**, não para fornecedor privado de software:

| Fonte | O que diz |
|---|---|
| Termo de Adesão MNI — STF (VF 2024) | Só aderem órgãos **com credenciamento do art. 246 §2 do CPC**: administração direta/indireta, MP, Defensoria, Advocacia Pública |
| TRF6 — página oficial do MNI | Exige CNPJ, **IP público**, "Gestor de Negócio" com **matrícula funcional**, e-mail institucional e **delegação formal de competência** |
| eproc / TRF4 | Webservice MNI descrito como autorizado apenas a **órgãos do Poder Judiciário** |
| Docs do PJe — MNI Client | `entregarManifestacaoProcessual` exposto a **sistemas** com role `invoke-service-endpoint` concedida pelo tribunal |

Reforço institucional: o CNJ já atende o advogado por outro caminho — o
**Escritório Digital** (CNJ + Conselho Federal da OAB, sobre MNI, consulta e
**envia petição**, gratuito). O intermediário oficial existe e é institucional.

Nenhuma dessas fontes diz "empresa privada não pode". Todas descrevem um
desenho em que ela não caberia. **Não é conclusão — é motivo para perguntar
antes de investir.**

### 0.1 A consulta que resolve isso (faça primeiro)

Destinatários: **DTI de dois tribunais** da lista da §1.1 + **`integracaopdpj@cnj.jus.br`**.

Pergunta, literal:

> Pessoa jurídica de direito privado, fornecedora de software de gestão para
> advogados, pode obter credencial de acesso ao webservice MNI para as operações
> `consultarProcesso` e `entregarManifestacaoProcessual`, atuando **em nome e
> por conta de advogado regularmente habilitado nos autos**? Em caso positivo,
> qual o procedimento e quais documentos são exigidos? Em caso negativo, existe
> caminho previsto para o advogado autorizar sistema de terceiro?

- [ ] Enviado ao tribunal A — data: ______ / resposta: ______
- [ ] Enviado ao tribunal B — data: ______ / resposta: ______
- [ ] Enviado ao `integracaopdpj@cnj.jus.br` — data: ______ / resposta: ______

**Se a resposta for negativa nos três:** a trilha MNI morre, o `MniFilingDriver`
não deve ser construído, e o agente local passa a ser o único caminho de leitura
e protocolo. Isso **não** bloqueia o piloto — ver `estado.md`.

**Se for positiva:** siga a seção 2 normalmente.

---

## 1. O que foi verificado

Varredura de **303 URLs candidatas** (27 TJs × 7 padrões, 6 TRFs × 3, 24 TRTs
× 4). Critério de aprovação: o host serviu `wsdl:definitions` com
`targetNamespace = http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/`.

**16 URLs responderam**, que consolidam em **14 perfis `(tribunal, grau)`** —
TJPE 1º grau e TRF5 1º grau atendem por dois endereços cada
(`/1g/` e `/pje/`; `pje.` e `pje1g.`), e a tabela registra um por rota.

Todos na versão **2.2.2** e todos expondo as seis operações do MNI, incluindo
as duas que interessam ao Causor:

- `consultarProcesso` — leitura dos autos
- `entregarManifestacaoProcessual` — protocolo

### 1.1 Perfis registrados (14)

Espelham exatamente `backend/app/connectors/mni/profiles.py`; o teste
`test_todo_perfil_registrado_foi_verificado_contra_o_tribunal` impede que
entre ali qualquer endereço não confirmado.

| Tribunal | Grau | Endpoint |
|---|---|---|
| TJAP | 1 | `https://pje.tjap.jus.br/1g/intercomunicacao` |
| TJAP | 2 | `https://pje.tjap.jus.br/2g/intercomunicacao` |
| TJES | 1 | `https://pje.tjes.jus.br/pje/intercomunicacao` |
| TJMT | 1 | `https://pje.tjmt.jus.br/pje/intercomunicacao` |
| TJPA | 1 | `https://pje.tjpa.jus.br/pje/intercomunicacao` |
| TJPE | 1 | `https://pje.tjpe.jus.br/1g/intercomunicacao` |
| TJPE | 2 | `https://pje.tjpe.jus.br/2g/intercomunicacao` |
| TJPI | 1 | `https://pje.tjpi.jus.br/1g/intercomunicacao` |
| TJPI | 2 | `https://pje.tjpi.jus.br/2g/intercomunicacao` |
| TJRR | 1 | `https://pje.tjrr.jus.br/pje/intercomunicacao` |
| TRF5 | 1 | `https://pje.trf5.jus.br/pje/intercomunicacao` |
| TRF5 | 2 | `https://pje2g.trf5.jus.br/pje/intercomunicacao` |
| TRF6 | 1 | `https://pje1g.trf6.jus.br/pje/intercomunicacao` |
| TRF6 | 2 | `https://pje2g.trf6.jus.br/pje/intercomunicacao` |

O TJMT expõe duas operações extras (`consultarClasseJudicialOutraInstancia`,
`consultarExpedientesProcesso`) — variação local, não usada pelo Causor.

### 1.2 O que **não** foi confirmado (e por quê importa)

`403` **não prova ausência de MNI** — prova WAF na frente do webservice, que é
o normal para serviço credenciado. Mas sem confirmação a rota tem de cair no
agente local, porque **falha de MNI marca a captura `failed` e não tem
fallback automático** (`executor.run_mni_capture_job`). Endpoint palpitado
manda o advogado para um erro em vez do caminho que funciona.

Por isso saíram da tabela de perfis:

- **TJMG, TJDFT, TJBA** — estavam registrados como palpite; TJMG redireciona
  para página de erro, os outros dois respondem 403.
- **Todos os 24 TRTs** — o padrão CSJT documentado pelo TRT-15
  (`/primeirograu/servicosweb/mni222/intercomunicacao`) responde 403 em toda a
  varredura. O padrão que estava no código
  (`/primeirograu/intercomunicacao`) responde **404** — estava simplesmente
  errado.

Padrões de URL testados, para quem for reverificar:

```
https://pje.<host>/pje/intercomunicacao          https://pje2g.<host>/pje/intercomunicacao
https://pje1g.<host>/pje/intercomunicacao        https://pje2i.<host>/pje/intercomunicacao
https://pje.<host>/1g/intercomunicacao           https://pje.<host>/2g/intercomunicacao
https://pje2.<host>/pje2g/intercomunicacao
https://pje.<host>/primeirograu/servicosweb/mni222/intercomunicacao   (CSJT)
https://pje.<host>/pje-integracao-api/mni300/intercomunicacao         (MNI 3.0.0)
```

### 1.3 Autenticação — confirmada como usuário/senha

Extraído do schema real do WSDL do TRF5:

```
tipoConsultarProcesso:
  idConsultante (string), senhaConsultante (string), numeroProcesso,
  dataReferencia?, movimentos?, incluirCabecalho?, incluirDocumentos?, documento*

tipoEntregarManifestacaoProcessual:
  idManifestante?, senhaManifestante?, numeroProcesso?, dadosBasicos?,
  documento+, dataEnvio, parametros*
```

Isso **confirma o desenho do `MniClient`** — ele envia exatamente
`idConsultante`/`senhaConsultante` ([client.py:33-38](../../backend/app/connectors/mni/client.py#L33-L38)) — e confirma os
campos da tela de Configurações (id consultante + senha).

**Ressalva:** o portal do TJMG descreve a autenticação como derivada de
certificado ICP-Brasil (CPF/CNPJ extraído do certificado). Se algum tribunal
do piloto exigir mTLS em vez de usuário/senha, o `MniClient` precisará de
suporte a certificado cliente. Confirmar no credenciamento antes de assumir.

### 1.4 WSDL acessível ≠ serviço funcional

Relato de campo consistente: a operação "leve" (`consultarProcesso` sem
documentos) costuma funcionar, e **é na entrega do teor dos documentos que os
tribunais falham**. Nenhum endpoint desta lista está provado ponta a ponta —
só o credenciamento real, rodando `RUN_MNI_LIVE=1`, promove um tribunal a
utilizável. A tabela de perfis diz "o endereço existe", não "funciona".

### 1.5 Como reverificar

O script da varredura está em `scripts/probe_mni.py`. Rode quando desconfiar
de um tribunal ou antes de registrar um perfil novo:

```powershell
cd backend
.\.venv\Scripts\python.exe ..\scripts\probe_mni.py
```

---

## 2. O ofício de credenciamento

### 2.1 Base normativa

Ofício redigido e pronto para preencher:
[`oficio-credenciamento-mni.md`](oficio-credenciamento-mni.md).

- **Resolução Conjunta CNJ/CNMP nº 3/2013** — institui o MNI como padrão de
  intercâmbio de informações processuais entre os órgãos do Judiciário, via
  webservice. É a norma-mãe a citar.
- **Provimento 355/2018** (citado pelo TJMG) — Código de Normas da
  Corregedoria, que fundamenta o acesso via MNI. **É específico do TJMG**;
  para outro tribunal, troque pelo Código de Normas local.
- **Lei 11.419/2006, art. 1º, §2º, III** — reconhece como assinatura
  eletrônica válida o **cadastro de usuário no Poder Judiciário**. É o
  dispositivo que pode dispensar PJeOffice/certificado no protocolo via MNI.
  **Confirmar com o tribunal**, porque depende de regulamento local.

### 2.2 Escolha do tribunal do piloto

Priorize, nesta ordem:

1. **Tribunal onde o advogado do piloto tem processos ativos** — sem isso não
   há o que capturar.
2. **Tribunal na lista da seção 1.1** — endpoint já confirmado, um risco a
   menos.

Cruzando os dois critérios: **TJPE, TJPI e TJAP** são os melhores candidatos
entre os estaduais (1º e 2º grau confirmados), e **TRF5/TRF6** entre os
federais. Se o piloto for TJMG ou trabalhista, o endpoint terá de ser obtido
no próprio credenciamento — o que não é problema, já que a URL vem no
deferimento.

### 2.3 Destinatário

**Diretoria/Secretaria de Tecnologia da Informação** do tribunal. Alguns
tribunais têm formulário próprio ("acesso automatizado por sistemas
externos"); procure isso antes de protocolar ofício genérico.

### 2.4 O que pedir (checklist)

> Já incorporado ao ofício em
> [`oficio-credenciamento-mni.md`](oficio-credenciamento-mni.md) — este
> checklist serve para conferir antes de enviar.

- [ ] Acesso ao **webservice MNI**, versão **2.2.2**, para o sistema Causor.
- [ ] Operações: **`consultarProcesso`** (com `incluirDocumentos=true`) e
      **`entregarManifestacaoProcessual`**.
- [ ] Identificação do advogado responsável: **nome, CPF, OAB/UF**.
- [ ] Identificação do sistema consumidor: **Causor**, com finalidade
      (automação de acompanhamento processual e peticionamento do próprio
      advogado, nos processos em que ele já atua).
- [ ] Ambiente de **homologação** antes de produção, se houver.

### 2.5 O que perguntar no mesmo ofício

Estas respostas destravam decisões de arquitetura — perguntar agora evita
retrabalho:

1. Qual a **URL exata** do endpoint MNI de 1º e 2º grau (produção e
   homologação)?
2. A autenticação é por **usuário/senha** (`idConsultante`/`senhaConsultante`)
   ou exige **certificado ICP-Brasil** no canal (mTLS)?
3. O `consultarProcesso` com `incluirDocumentos=true` devolve o **teor
   (conteúdo binário)** dos documentos, ou só os metadados? *(este é o ponto
   que mais falha na prática)*
4. Há **limite de requisições** (rate limit, janela de horário)?
5. O `entregarManifestacaoProcessual` via MNI dispensa assinatura por
   certificado, nos termos do **art. 1º, §2º, III da Lei 11.419/2006**, sendo
   o próprio credenciamento a assinatura eletrônica? *(a resposta pode
   eliminar o gargalo do PJeOffice)*
6. A resposta do `entregar` traz **número e comprovante de protocolo**?

### 2.6 Depois do deferimento

1. Configurações → Acesso aos tribunais → **Conectar novo tribunal**: cadastre
   tribunal, id consultante e senha. A senha vai direto para o vault; o banco
   guarda só a referência.
2. Clique **Testar** informando um número CNJ real de processo do advogado.
3. Se a URL informada pelo tribunal for diferente da tabela em `profiles.py`,
   **corrija o perfil** antes de testar — o campo `verificado` só deve ficar
   `True` para endereço confirmado.
4. Rode o teste live opt-in:

```powershell
cd backend
$env:RUN_MNI_LIVE=1
.\.venv\Scripts\python.exe -m pytest tests/live/test_mni_live.py
```

5. Com o teste verde, o roteamento passa a escolher `fonte="mni"` sozinho
   para os processos daquele tribunal ([autos/service.py:60](../../backend/app/autos/service.py#L60)).
   Nada mais precisa ser configurado.

---

## Fontes

- WSDL ao vivo do TRF5 (`https://pje.trf5.jus.br/pje/intercomunicacao?wsdl`) —
  schema de autenticação e operações, lido em 2026-07-22.
- [Modelo Nacional de Interoperabilidade — Portal CNJ](https://www.cnj.jus.br/tecnologia-da-informacao-e-comunicacao/comite-nacional-de-gestao-de-tecnologia-da-informacao-e-comunicacao-do-poder-judiciario/modelo-nacional-de-interoperabilidade/)
- [MNI-PJe — Portal TJMG](https://www.tjmg.jus.br/portal-tjmg/acoes-e-programas/gestao-de-primeira/processo-judicial-eletronico-fluxo-unificado-civel/modelo-nacional-de-interoperabilidade-mni-pje.htm)
- [Dados Abertos — TRT15](https://trt15.jus.br/transparencia/dados-abertos) (padrão CSJT de URL)
- [Integração PJe/MNI: Nem Todo Tribunal Está Pronto](https://tecjustica.substack.com/p/integracao-pjemni-nem-todo-tribunal)
- [Serviço MNI Client — Documentação PJe](https://docs.pje.jus.br/servicos-auxiliares/servico-mni-client/)
