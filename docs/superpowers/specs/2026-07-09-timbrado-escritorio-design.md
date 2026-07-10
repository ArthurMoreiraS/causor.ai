# Design: Papel timbrado por escritório

- **Data:** 2026-07-09
- **Status:** aprovado (brainstorming com o usuário)
- **Escopo:** renderer de PDF com identidade visual do escritório + configuração na UI + preview do PDF antes do protocolo

## Contexto e motivação

Hoje o PDF de protocolo sai de `backend/app/filing/render.py`: um gerador
artesanal de PDF 1.4 (sem biblioteca), uma fonte (Helvetica 10pt), cabeçalho
fixo "Causor - Minuta para protocolo". Escritório nenhum protocola peça que
não pareça dele — na prática o advogado precisaria copiar o texto para o Word,
aplicar o timbrado e exportar de novo, quebrando o fluxo
aprovar → assinar → protocolar que é o coração do produto.

Além disso, o PDF só nasce dentro do job de protocolo
(`backend/app/queue/jobs.py`): o advogado aprova a minuta na UI sem nunca ver
a peça final. O timbrado foi cobrado nominalmente pelo advisor jurídico
(julho/2026) e é o único item da lista dele que se fecha sem dependência
externa.

## Decisões tomadas (com o usuário, 2026-07-09)

1. **Configuração via UI completa** no SettingsModal (seção Perfil do
   software) existente (upload de logo + campos de texto), persistida no
   `escritorio`.
2. **Preview:** botão "Baixar PDF" na petição, servido por endpoint novo que
   renderiza sob demanda.
3. **Conjunto visual padrão:** logo + cabeçalho em texto + rodapé em texto,
   layout fixo. Sem cores/fontes por escritório, sem upload de template.
4. **Motor de PDF: fpdf2** — Python puro, sem dependência de sistema (instala
   limpo no Render e no Windows), hooks nativos de cabeçalho/rodapé por
   página, embute PNG/JPEG. ReportLab (poder extra desnecessário) e
   WeasyPrint (dependências nativas Pango/GDK) foram descartados.

## Modelo de dados

Quatro colunas novas, todas nullable, na tabela `escritorio`
(migração Alembic):

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `timbrado_logo` | LargeBinary | imagem normalizada no upload |
| `timbrado_logo_mime` | String(30) | mime do logo armazenado (`image/png` após a normalização) |
| `timbrado_cabecalho` | Text | linhas livres sob o nome (endereço, telefone, e-mail) |
| `timbrado_rodape` | Text | texto livre (OABs, site) |

O nome do escritório já existe (`escritorio.nome`) e encabeça o timbrado.
Todo campo é opcional: o render usa o que estiver preenchido.

## Renderer (`backend/app/filing/`)

O gerador artesanal é **substituído por um único caminho fpdf2**. A assinatura
pública é preservada e estendida:

```python
render_minuta_pdf(texto: str, *, meta: dict | None = None,
                  timbrado: TimbradoEscritorio | None = None) -> bytes
```

- `TimbradoEscritorio` é um dataclass (nome, linhas de cabeçalho, rodapé,
  logo bytes + mime). O renderer continua **função pura** — sem acesso a
  banco; quem chama monta o dataclass.
- Um helper `load_timbrado(session, escritorio_id) -> TimbradoEscritorio | None`
  (em `app/filing/`) constrói o dataclass a partir do `Escritorio`; usado
  pelo job de protocolo e pelo endpoint de PDF.
- **Sem timbrado** → layout neutro equivalente ao atual ("Causor - Minuta
  para protocolo" + metadados de processo/tipo/tribunal). Nada muda para quem
  não configurou.
- **Com timbrado** → logo + nome + cabeçalho no topo de **toda página**
  (hook `header()` do fpdf2), rodapé com o texto do escritório +
  "página X de Y" em toda página (hook `footer()` + `alias_nb_pages`),
  corpo com margens adequadas e quebra de página automática.

Detalhes técnicos:

- **Fonte Unicode embarcada** (DejaVu Sans, com subsetting no PDF): minutas
  geradas por LLM trazem aspas curvas e travessões fora do latin-1, que
  quebrariam as fontes core do PDF. A fonte embarcada elimina essa classe de
  erro. Os arquivos `.ttf` entram no repositório em `backend/app/filing/fonts/`.
- **Normalização do logo no upload** (Pillow, dependência transitiva do
  fpdf2): aceita PNG/JPEG de até 2MB; re-encoda para PNG, remove metadados,
  limita a largura a 1000px. Resultado armazenado tipicamente ≤300KB. Garante
  que o render nunca falha por imagem ruim e mantém o PDF pequeno — tribunais
  PJe impõem limite de MB por arquivo.

## API

- **Perfil operacional (endpoints existentes de GET/PATCH):**
  - GET devolve os campos de timbrado; logo como base64.
  - PATCH aceita `timbrado_cabecalho`, `timbrado_rodape` e `timbrado_logo`
    (base64; `null` remove o campo). Validação no upload: magic bytes
    PNG/JPEG, cap de tamanho, 422 com mensagem clara se inválido.
  - Mudanças registradas no audit log, como já ocorre para nome/CNPJ.
- **Novo endpoint `GET /peticoes/{id}/pdf`:** renderiza a minuta sob demanda
  com o timbrado do tenant; responde `application/pdf` com
  `Content-Disposition` de download (`minuta-<processo>.pdf`). Isolamento
  multi-tenant via `get_owned_or_404`.
- **Job de protocolo (`jobs.py`):** carrega o timbrado do escritório da
  petição e o passa ao renderer — o PDF protocolado é idêntico ao do preview.

## Frontend

- **SettingsModal (seção Perfil do software):** nova seção "Papel timbrado" —
  upload de imagem com thumbnail de preview, textareas de cabeçalho e rodapé,
  salvando pelo PATCH existente. Validação client-side de tipo e tamanho
  antes do envio.
- **Tela da petição:** botão "Baixar PDF" que chama o endpoint novo com auth
  e dispara o download do blob.

## Testes (TDD)

- **Renderer:** com timbrado completo; sem timbrado (formato neutro
  preservado); texto multi-página (rodapé/paginação em todas); caracteres
  Unicode (aspas curvas, travessão); logo fixture mínima (PNG 1×1).
- **API:** PATCH rejeita tipo errado e tamanho estourado; GET do perfil
  devolve logo em base64; `GET /peticoes/{id}/pdf` devolve `application/pdf`
  e responde 404 para petição de outro tenant.
- **Job:** pacote de protocolo sai com o PDF timbrado quando o escritório tem
  timbrado configurado.

## Fora de escopo (v1)

- Export DOCX sobre modelo do escritório.
- Cores/fontes personalizadas por escritório.
- Upload de template visual pronto (PDF/imagem de fundo).
- PDF/A (validar necessidade no tribunal do piloto antes de investir).

## Riscos e observações

- **Limite de tamanho por tribunal:** a normalização do logo mantém a peça
  típica bem abaixo dos limites usuais do PJe; validar no tribunal do piloto.
- **Dependência nova:** `fpdf2` (traz Pillow). Sem dependência de sistema.
- **Determinismo:** os testes validam por texto extraído (pypdf), não por
  bytes; a data de criação real do fpdf2 é mantida como evidência de
  protocolo.
