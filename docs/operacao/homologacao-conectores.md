# Homologação de conectores judiciais

Este runbook descreve como validar um perfil de conector `(sistema, tribunal,
grau)` com uma conta real, de forma read-only, antes de promovê-lo a
`supported`. Nada aqui roda na CI: os testes live são opt-in e executados na
máquina autorizada do advogado, com o agente local já pareado e logado.

## Pré-requisitos

- Agente local pareado e online (`python -m app.local_agent run`).
- Sessão do tribunal já estabelecida pelo login unificado (janela do portal
  aberta pelo Causor ou `python -m app.local_agent login ...`).
- Registro de conta preenchido (fica **fora** do Git):

```yaml
sistema: PJe | EPROC | e-SAJ | Projudi
tribunal: SIGLA
grau: "1" | "2"
url_login: https://...
processo_teste: numero CNJ
sigiloso: true | false
permite_leitura: true
permite_upload_rascunho: true | false
permite_protocolo: false      # sempre false durante a descoberta
responsavel_juridico: nome interno
janela_de_teste: ISO-8601
```

## Passo 1 — Leitura read-only (obrigatório)

```powershell
$env:RUN_COURT_LIVE='1'
$env:CAUSOR_LIVE_SYSTEM='PJe'
$env:CAUSOR_LIVE_COURT='TJMG'
$env:CAUSOR_LIVE_DEGREE='1'
$env:CAUSOR_LIVE_PROCESS='numero-autorizado-no-agente-local'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_reader_live.py -v -k live_reader
```

Espera-se: o manifesto vem completo (`cursor_complete=True`) e a enumeração
repetida produz o mesmo `source_fingerprint`. O número do processo é redigido
para os quatro últimos dígitos ao registrar a validação; trace vai para
`%LOCALAPPDATA%\Causor\traces\{profile_key}\{timestamp}.zip`, nunca para o
repositório.

## Passo 2 — Preparo de protocolo (`submit=false`)

Somente depois do Passo 1 passar. Usa um PDF de teste e **para antes** do
primeiro clique irreversível:

```powershell
$env:CAUSOR_LIVE_PETITION_PDF='C:\caminho\peticao-teste.pdf'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_filing_live.py -v
```

Espera-se: `checkpoint == "ready_to_sign"` e `irreversible is False`.

## Stop conditions

Interrompa e devolva o controle ao advogado em qualquer um: CAPTCHA, sessão
expirada, acesso negado, documento sigiloso listado mas não baixável,
paginação sem marcador de término, download vazio/HTML no lugar de PDF, hash
divergente, layout sem perfil aprovado, assinador pedindo PIN/OTP fora da
janela, ou comprovante/número de protocolo não verificável.

## Desenvolvimento sem acesso real

Os simuladores sanitizados (`app.connectors.simulators`) servem páginas
sintéticas com documentos fixos `SIM-DOC-001..003` (um anexo aninhado, um
sigiloso) e PDFs sem dado real. Use-os para desenvolver drivers e rodar os
testes de simulador na CI antes de qualquer teste live.
