# Proxima sessao - PJe assistido

## Decisao atual

Nao implementar o Playwright/PJe agora. Guardar o desenho para retomar depois.

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

## Como o PJe assistido deve funcionar

1. Advogado gera e revisa a minuta no Causor.
2. Advogado aprova no Gate OAB.
3. Advogado clica em `Preparar protocolo PJe`.
4. O Causor abre uma sessao Playwright assistida.
5. O advogado faz login diretamente no PJe real, nao em formulario do Causor.
6. O Causor salva apenas o `storage_state`/sessao no vault.
7. O Causor localiza o processo.
8. O Causor abre peticionamento intermediario.
9. O Causor seleciona tipo de peticao.
10. O Causor anexa minuta/documentos.
11. O fluxo para em `ready_to_sign`.
12. O advogado assina/envia no PJe/PJeOffice.
13. O advogado registra o numero do protocolo no Causor.
14. O Causor marca a peticao como `protocolada` e registra auditoria.

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

Primeiro modo: `manual_pjeoffice`.

- Causor prepara tudo.
- Para na tela de assinatura.
- Advogado assina/envia no PJe/PJeOffice.
- Advogado registra o protocolo no Causor.

Modo futuro: `cloud_certificate`.

- Integrar BirdID, Certisign, Soluti, Safeweb, Valid ou outro provedor
  ICP-Brasil em nuvem.
- Guardar apenas token/referencia no Supabase Vault.
- Advogado confirma via push/OTP quando exigido.

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
