# Login multi-sistema robusto + sessão viva — Design

> **Status:** aprovado, não implementado. Data: 2026-07-29.
> Primeiro bloco de um programa maior (ver §9). Escopo desta spec: **só login e
> estado de sessão**. Leitura de autos e protocolo ficam para specs próprias.

## 1. Problema

Duas afirmações que motivaram este trabalho foram verificadas no código e são
verdadeiras:

1. **Nenhum conector foi testado contra tribunal real.** `register_reader` /
   `register_filing` só são chamados em testes; `handle_read_process` e
   `handle_prepare_filing` levantam `NotImplementedError` para **todos** os
   sistemas, PJe inclusive. Os simuladores foram escritos a partir de
   suposições, não de observação.
2. **A detecção de login está quebrada**, em duas cópias independentes e em
   direções opostas (§3).

O que **não** é verdade é que a arquitetura seja PJe-only: `contracts.py`,
`registry.py`, `court_routing.py`, `sessions.py` e os simuladores já são
neutros de sistema. O que falta é implementação, não estrutura — mais três
vieses pontuais de PJe listados em §5.

Além disso, **nada no sistema jamais verifica se uma sessão continua viva**:
`mark_session_expired()` existe, está documentado como "chamado quando
leitura/protocolo/health-check detecta sessão inválida", e é chamado
**somente em testes**. O estado `"expirado"` é hoje inalcançável em produção.

## 2. Decisões travadas com o Arthur

| Decisão | Escolha |
|---|---|
| Modelo de login | **Manual robusto + sessão viva.** O Causor continua não digitando credencial; o advogado loga uma vez por tribunal e o sistema mantém/afere a sessão. |
| Sinal primário de detecção | **Seletor visível no DOM**, não substring no HTML. |
| Tribunal não verificado | **Degrada para confirmação humana**, nunca para falso negativo. |
| Verificação real | Só **eproc/TJTO** nesta leva (é o único acesso que temos). |

## 3. O bug, nas duas cópias

### 3.1 `local_agent/handlers.py::_page_state` — falso negativo

```python
_LOGIN_MARKERS = ("entrar com gov.br", "certificado digital", "senha")
_AUTHENTICATED_MARKERS = ("logout", "sair", "painel", ...)
if authenticated and not unauthenticated:   # <-- exige AUSÊNCIA de "senha"
    return "authenticated"
```

Painel logado de eproc e de PJe tem **"Alterar Senha"** no menu. A substring
`"senha"` aparece, `unauthenticated` vira `True`, e a função nunca confirma o
login: o advogado loga, e o agente gira 300s até devolver `login_timeout`.

### 3.2 `connectors/pje/pages/login.py::ensure_session_valid` — falso positivo

```python
authenticated_markers = ("logout", "sair", "painel", "processo")
```

`"processo"` aparece na **tela de login** de vários tribunais. A sessão morta
é classificada como válida e o fluxo segue adiante. É o mais perigoso dos
dois, porque falha para o lado do "parece que deu certo".

### 3.3 Por que seletor resolve por construção

`input[type=password]` **não existe** num painel autenticado, mesmo que as
palavras "Alterar Senha" apareçam num link de menu. Trocar substring-no-HTML
por seletor-visível elimina as duas famílias de erro sem lista de exceções.

## 4. Arquitetura

### 4.1 Novo: `backend/app/connectors/login_profiles.py`

Fonte única de verdade da detecção. Mesmo padrão de `mni/profiles.py`
(registro fail-closed + teste que exige evidência para `verificado=True`).

```python
@dataclass(frozen=True)
class LoginProfile:
    sistema: str
    authenticated_selectors: tuple[str, ...]   # ex.: "a[href*='logout']"
    login_selectors: tuple[str, ...]           # ex.: "input[type='password']"
    captcha_selectors: tuple[str, ...]
    verificado: bool = False

def resolve_login_profile(sistema: str) -> LoginProfile | None: ...

def classify_page_state(
    *, authenticated: bool, login: bool, captcha: bool
) -> str:  # "authenticated" | "login" | "captcha" | "inconclusive"
```

`classify_page_state` é **função pura** — recebe três booleanos já apurados
pelo chamador e não conhece Playwright. Isso a torna testável sem navegador e
permite que agente e conector compartilhem a mesma regra.

**Precedência:** `captcha` → `login` (formulário visível = ainda esperando) →
`authenticated` → `inconclusive`.

### 4.2 Modificado: `local_agent/handlers.py`

- `handle_open_court_login` passa a usar `resolve_login_profile(sistema)` +
  `locator.is_visible()` em vez de substring.
- Sem perfil para o sistema, ou `inconclusive` por mais de 30s → **banner de
  confirmação** (§4.5).
- **Novo** `handle_check_court_session`: headless, abre o perfil persistente,
  navega ao `url_login` da rota, classifica e devolve `session_alive: bool`.

### 4.3 Modificado: `connectors/pje/pages/login.py`

`ensure_session_valid` deixa de ter marcadores próprios e passa a consumir
`login_profiles`. Deduplicação: uma regra, dois chamadores.

### 4.4 Modificado: `connectors/sessions.py`

- `request_session_check(...)` — enfileira `check_court_session` **para uma
  rota**, espelhando `request_court_login` (mesma idempotência por rota/hora).
- `apply_session_check_result(...)` — `authenticated` atualiza
  `last_confirmed_at` e mantém `conectado`; qualquer outro desfecho chama o
  `mark_session_expired()` que hoje está órfão.

Sem migração de banco: `status` já aceita `"expirado"` e `last_confirmed_at`
já existe.

#### Quem dispara a checagem

Dois gatilhos, ambos **por rota** (nunca uma varredura de todas as rotas):

1. **Sob demanda, antes da ação** — o fluxo que vai chamar `read_process` ou
   `prepare_filing` numa rota com `status="conectado"` pede a checagem antes.
   É o gatilho que evita começar uma captura longa com sessão morta.
2. **Manual pela UI** — botão "verificar agora" em Configurações → Acesso aos
   tribunais, por rota.

**Varredura periódica (cron) fica fora desta spec.** É onde o risco de lock do
perfil (§11) mais aparece — um cron abrindo perfis headless enquanto o
advogado usa o navegador — e não é necessária para o objetivo: as duas
entradas acima já mantêm `last_confirmed_at` honesto nos momentos em que ele
importa. Entra depois, se a operação real mostrar necessidade.

### 4.5 Confirmação humana (a rede)

Quando a detecção é inconclusiva, o agente injeta um banner fixo **na própria
janela local** com o botão "Já estou logado", e aguarda o clique. Só renderiza
no navegador do agente; não altera nem envia nada ao sistema do tribunal.

Justificativa: tribunal que nunca vimos não pode virar `login_timeout`. O
mesmo princípio do gate de aprovação humana — quando a máquina não tem
certeza, quem decide é a pessoa.

## 5. Vieses de PJe a remover nesta leva

| Local | Hoje | Vira |
|---|---|---|
| [`court_routing.py:217`](../../../backend/app/capture/court_routing.py#L217) | tribunal desconhecido → `sistema="PJe"` | fail-closed (sistema desconhecido explícito) |
| [`assistant.py:43`](../../../backend/app/connectors/assistant.py#L43) | `processo.sistema or route.sistema or "PJe"` | sem default silencioso de PJe |
| `CAUSOR_PJE_ALLOW_PROD` | trava de produção só nomeada/aplicada a PJe | `CAUSOR_COURT_ALLOW_PROD`, válida para os 4 sistemas (aceitar o nome antigo por compatibilidade) |

A terceira é a mais relevante para segurança: hoje **eproc, e-SAJ e Projudi não
têm trava nenhuma** contra abrir tribunal de produção por engano.

## 6. Interação com o MNI (verificada, sem conflito)

[`assistant.py:65`](../../../backend/app/connectors/assistant.py#L65) já decide
a precedência: rota com perfil MNI **e** credencial ativa retorna
`capture_autos` direto, pulando pareamento e login de portal. Esse é o
**único** ponto de decisão entre MNI e agente, e o `AGENTS.md` proíbe criar um
segundo.

Esta spec **não toca nisso**. A checagem de sessão viva só é pedida para uma
rota que **já tem linha em `CourtSessionState` com `status="conectado"`** — e
rota servida por MNI nunca cria essa linha (esse estado é, por definição,
"sessão de navegador na máquina do advogado"). A exclusão do MNI é por
construção: em nenhum ponto o código pergunta "isto é MNI?" para decidir
sobre sessão.

## 7. Perfis iniciais e política de `verificado`

| Sistema | Origem do perfil | `verificado` |
|---|---|---|
| **EPROC** | observação direta do TJTO (acesso real disponível) | `True` |
| PJe | melhor conhecimento, sem conta | `False` |
| e-SAJ | melhor conhecimento, sem conta | `False` |
| Projudi | melhor conhecimento, sem conta | `False` |

Perfil `verificado=False` **funciona** — só não confirma sozinho: cai na
confirmação humana. Um teste espelhando
`test_todo_perfil_registrado_foi_verificado_contra_o_tribunal` (do MNI) impede
marcar `verificado=True` sem evidência registrada. É a trava que evita repetir
o erro de 2026-07-21 (perfis MNI palpitados que respondiam 404).

## 8. Testes

- **Puros (sem navegador):** matriz de `classify_page_state`, incluindo
  explicitamente os dois bugs — painel com "Alterar Senha" deve dar
  `authenticated`; tela de login contendo "processo" **não** pode dar
  `authenticated`.
- **Simulador:** os simuladores existentes (`eproc`, `pje`, `esaj`, `projudi`)
  ganham página de login e painel com a estrutura DOM que os seletores esperam.
- **Live opt-in:** `RUN_COURT_LIVE=1` contra o eproc real do TJTO, read-only —
  login, confirmação e checagem de sessão viva. Nenhum teste live escreve nada
  no tribunal.

## 9. Fora de escopo (e por quê)

- **Login automático com credencial guardada** — decidido: manual.
- **`EprocReaderDriver` / leitura de autos** — próximo bloco; depende deste.
- **Protocolo (filing)** — irreversível; a regra do repo é não projetar a
  verificação de comprovante sem ter visto um comprovante real.
- **Verificar PJe/e-SAJ/Projudi** — sem conta, marcar como verificado seria
  exatamente o erro que a §7 previne.
- **Varredura de webservice multi-sistema** — bloco separado. Registro aqui o
  achado que a motiva: o `scripts/probe_mni.py` só testa padrões de URL do PJe,
  e a sondagem de 2026-07-29 mostrou que o eproc expõe webservice num padrão
  totalmente diferente (`/ws/controlador_ws.php?srv=...`), com hosts dedicados
  vivos (`eproc1g-ws.tjto.jus.br`, `eproc2g-ws.tjto.jus.br`) que respondem XML
  do eproc. O nome de serviço MNI do eproc não é o do PJe e deve ser obtido com
  a DTI do tribunal, não por tentativa.

## 10. Achado registrado: código morto

`connectors/pje/session.py::PjeBrowserSession` depende de `storage_state`, cuja
única fonte (o cofre de sessão do backend) foi removida — conforme o próprio
docstring de `connectors/drivers.py`. A classe é inalcançável em produção.
Fica registrado; a remoção não entra nesta spec para não misturar limpeza com
a mudança de comportamento.

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Chromium trava o `user_data_dir`; checagem headless conflita com janela headed aberta no mesmo perfil | Serializar por perfil (o agente já processa um comando por vez) e tratar o lock como `inconclusive`, **nunca** como `expirado` — derrubar sessão boa é pior que não checar |
| Seletores mudam quando o tribunal atualiza o portal | `verificado` + validação live opt-in; falha vira `inconclusive` → confirmação humana, não erro |
| Perfis não verificados (PJe/e-SAJ/Projudi) errarem os seletores | Por design não quebram nada: caem na confirmação humana |
