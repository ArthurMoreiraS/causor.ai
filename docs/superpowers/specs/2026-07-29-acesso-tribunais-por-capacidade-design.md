# Acesso aos tribunais organizado por capacidade — Design

> **Status:** aprovado, não implementado. Data: 2026-07-29.
> Substitui a proposta anterior de "painel diagnóstico por canal", que ainda
> organizava a tela por tecnologia. Ver §2 para o motivo da virada.

## 1. O problema, dito pelo próprio operador

A tela atual de Configurações apresenta duas seções — "Credencial oficial do
tribunal" e "Computador do advogado" — e o Arthur, que **construiu o sistema**,
disse não entender a divisão. Se o operador não entende, o advogado não tem
chance.

O diagnóstico não é falta de texto explicativo (o `MniSection` até explica bem
o benefício). É que **a tela está organizada por como o Causor se conecta, e
não pelo que o advogado consegue fazer**.

### 1.1 O objetivo real do acesso

Acessar o sistema do tribunal serve a exatamente duas coisas:

1. **Buscar o contexto completo dos autos** — para a minuta ser escrita com
   base no processo real.
2. **Protocolar a peça.**

O advogado quer um fluxo só: **cria a minuta → aprova → protocola**, e o
contexto é buscado sozinho no meio disso. Esse fluxo **já existe** no produto
(§5). O que atrapalha é a tela de Configurações apresentar, em paralelo, um
modelo mental técnico que compete com ele.

### 1.2 O fato que nenhuma tela conta hoje

Verificado no código: **`MniFilingDriver` não existe.** `connectors/drivers.py`
é explícito — *"protocolo real de {sistema} roda no agente local, não no
backend"*. E o `docs/estado.md` confirma: *"Hoje só o agente local protocola"*.

Consequência que muda tudo:

> **Protocolar exige o computador pareado. Sempre. Em todo tribunal. Inclusive
> onde há credencial oficial.**

A credencial oficial cobre **só a leitura**. A tela atual não diz isso em lugar
nenhum, e é exatamente por isso que "Credencial oficial — Recomendada" parece
resolver o problema inteiro e a segunda seção parece redundante.

## 2. A virada de enquadramento

| Antes (proposta anterior) | Agora |
|---|---|
| Organizar por **canal** (oficial × agente) | Organizar por **capacidade** (ler autos × protocolar) |
| Jargão aceitável (público = operador) | Linguagem simples; termo técnico só como complemento |
| Duas seções técnicas mantidas como estão | Duas seções viram *ação*, não *conceito* |

O advogado nunca precisa saber a palavra "MNI". Ele precisa saber, por
tribunal: **consigo redigir? consigo protocolar? se não, o que falta?**

## 3. O modelo de capacidade

Por rota `(tribunal, grau)`, duas capacidades independentes:

| Capacidade | Quem atende | Estado possível |
|---|---|---|
| **Ler os autos** | canal oficial (se credenciado) **ou** computador pareado | pronto / falta conectar / sessão expirada |
| **Protocolar** | **somente** computador pareado | pronto / falta parear / sessão expirada |

A assimetria é a informação mais valiosa da tela, e some quando se organiza por
tecnologia.

## 4. Arquitetura

### 4.1 Decisão única, extraída

A ordem de decisão hoje está enterrada dentro de `assistant.resolve_next_step`.
Se a tela recalcular, diverge do que o sistema faz na hora H — e o `AGENTS.md`
proíbe segundo ponto de decisão. Extrair:

```python
# app/connectors/access_channel.py

@dataclass(frozen=True)
class Capacidade:
    disponivel: bool
    via: str | None       # "oficial" | "computador" | None
    falta: str | None     # "conectar_credencial" | "parear" | "logar" | "credenciamento"

@dataclass(frozen=True)
class AcessoTribunal:
    sistema: str
    tribunal: str
    grau: str
    ler_autos: Capacidade
    protocolar: Capacidade
    mni_disponivel: bool   # tribunal TEM perfil MNI, com ou sem credencial
    processos: int

def resolve_acesso_tribunal(
    session, *, escritorio_id, sistema, tribunal, grau
) -> AcessoTribunal: ...
```

`resolve_next_step` passa a **consumir** essa função em vez de decidir. Uma
decisão, dois consumidores.

### 4.2 Endpoint

`GET /tribunais/acesso` — agrega por `(tribunal, grau)` a partir dos
`ProcessoInstancia` do escritório (é onde o grau existe; `Processo` sozinho não
tem). Ordena por número de processos afetados: o que trava mais casos primeiro.

### 4.3 A tela

Bloco único no topo de Configurações, substituindo a apresentação atual:

```
Seus tribunais                                        2 de 4 prontos

TJTO · 1º grau                          12 processos      ⚠ Ação necessária
   Ler os autos    ✓  pelo seu computador
   Protocolar      ⚠  a sessão expirou            [ Reconectar ]

TJMT · 1º grau                           8 processos      ✓ Pronto
   Ler os autos    ✓  direto do tribunal (não usa seu computador)
   Protocolar      ✓  pelo seu computador

TJSP · 1º grau                           5 processos      ⚠ Ação necessária
   Ler os autos    ✗  falta conectar
   Protocolar      ✗  falta conectar              [ Conectar ]

TJPI · 1º grau                           2 processos      ✓ Pronto
   Ler os autos    ✓  pelo seu computador
                      este tribunal aceita leitura direta — pedir acesso
                      deixa a captura mais rápida e sem depender do
                      seu computador         [ Ver como pedir ]
   Protocolar      ✓  pelo seu computador
```

Três coisas que essa forma resolve e a atual não:

- **"pelo seu computador" aparece em toda linha de Protocolar**, em todo
  tribunal. A dependência fica óbvia sem ninguém explicar.
- **O TJPI** mostra o único caso em que a credencial oficial vale a pena pedir
  — e como uma *melhoria*, não como pré-requisito. Hoje essa informação não
  existe em lugar nenhum.
- **Nenhuma linha usa a palavra MNI.**

### 4.4 As duas seções atuais

Não são apagadas nem reescritas por dentro — viram **ação, não conceito**:

- Descem para um bloco recolhido **"Configuração avançada"**, abaixo do painel.
- Os botões do painel (`Conectar`, `Reconectar`, `Ver como pedir`) levam
  direto à ação certa, então o caminho normal nunca passa por lá.
- Títulos reescritos para dizer o que fazem, não o que são:
  - "Credencial oficial do tribunal" → **"Leitura direta pelo tribunal"**
  - "Computador do advogado" → **"Computador que executa os protocolos"**

## 5. Relação com o fluxo único (o que já existe)

O fluxo que o Arthur descreveu — *"cria a minuta, aprova e protocola, e o
software pega o contexto na hora"* — **já está construído**:

```
gate de contexto (fail-closed)  →  AcessoTribunalWizard (JIT)  →  minuta
                                                              →  aprovação
                                                              →  protocolo
```

O `AcessoTribunalWizard` já pede pareamento/login **só quando falta** e já pula
esses passos quando a rota tem credencial oficial.

**Esta spec não mexe nesse fluxo.** Ela conserta a tela que competia com ele.
O painel é onde se responde *"estou pronto?"* fora do calor do momento; o
wizard continua sendo o caminho normal, dentro do fluxo.

Um ajuste pequeno no wizard, para coerência de linguagem: onde hoje ele diz
"agente local", passa a dizer "seu computador" — mesmo vocabulário do painel.

## 6. Testes

- **Puros:** matriz de `resolve_acesso_tribunal` — com/sem perfil MNI ×
  com/sem credencial × agente online/offline × sessão conectada/expirada.
  Inclui a asserção que trava a assimetria: **`protocolar.via` nunca é
  `"oficial"`** enquanto `MniFilingDriver` não existir.
- **Regressão da decisão única:** teste que garante que `resolve_next_step` e o
  painel dão a mesma resposta para a mesma rota. É o que impede a divergência
  voltar.
- **Endpoint:** isolamento por `escritorio_id`; ordenação por nº de processos.
- **Frontend:** o painel renderiza os quatro estados (pronto, sessão expirada,
  não conectado, oficial disponível) e nenhum texto visível contém "MNI" nem
  "agente".

## 7. Fora de escopo

- **Construir o `MniFilingDriver`.** É o que tornaria o protocolo independente
  do computador do advogado, mas o `estado.md` é explícito: não antecipar, pois
  protocolo é irreversível e não se projeta verificação de comprovante sem ter
  visto um comprovante real.
- **Enviar ofício de credenciamento automaticamente.** O botão "Ver como pedir"
  abre o material que já existe em `areas/oficio-credenciamento-mni.md` com os
  dados do tribunal preenchidos. Enviar ofício a tribunal é ação externa
  irreversível.
- Reescrever o interior de `MniSection`/`AgentSection`, onboarding guiado para
  leigo, ação em massa sobre vários tribunais.

## 8. Risco

| Risco | Mitigação |
|---|---|
| Extrair a decisão mexe em caminho quente (`resolve_next_step` alimenta o gate de contexto) | O teste de regressão da decisão única (§6) compara as duas saídas; a extração é refactor puro, sem mudar a ordem das regras |
| Rota sem `ProcessoInstancia` não aparece no painel | É o comportamento correto: tribunal sem processo não é problema do advogado. O wizard cobre o caso do primeiro processo daquele tribunal |
| "2 de 4 prontos" pode sugerir que só o painel importa | O texto de estado sempre nomeia a capacidade afetada, nunca só um número |
