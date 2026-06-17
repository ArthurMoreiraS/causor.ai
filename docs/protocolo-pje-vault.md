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
