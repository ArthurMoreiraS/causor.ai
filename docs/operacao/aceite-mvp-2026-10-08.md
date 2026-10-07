# Aceite do MVP — primeiro caso

Prazo de trabalho: 08/10/2026. Critério: um advogado consegue preparar e revisar
uma minuta fundamentada nos documentos recebidos. Protocolo judicial e coleta
automática de autos não são necessários para esta aceitação.

## Preparação

- Confirmar login e `/me` no ambiente de piloto; `/health` sozinho não basta.
  Novo projeto Free migrado em 06/10, após autorização e confirmação de outra
  organização. Restore conferido e sessão técnica real validou `/me`, usuário,
  escritório e oito endpoints de produção. Frontend já usa o destino novo.
  Entrar novamente com a conta existente; senha/hash preservados, mas login
  com senha no navegador do fundador ainda não observado. Ver
  [migração](../historico/migracao-supabase-free-2026-10-06.md).
- Separar um caso autorizado, número/tribunal, cliente e polo representado,
  objetivo do trabalho, publicação/demanda e arquivos disponíveis.
- Preparar inventário externo dos arquivos: peça, versão, páginas e o que falta.
- Definir o advogado revisor e anotar o tempo habitual gasto nesse trabalho.

## Percurso

1. Em Intimações, capturar a OAB ou escolher publicação existente. Conferir teor,
   processo, disponibilidade/publicação e prazo. Revisar duração, termo inicial,
   calendário e data fatal; exceções não devem ser tratadas como prazo confirmado.
   Se a entrada for manual, cadastrar o trabalho em Trabalhos, com cliente e
   processo, e registrar o prazo conhecido quando aplicável.
2. Em Trabalhos, informar providência, polo e instruções. Em Documentos, usar
   Receber documentos → Enviar documentos. Aguardar processamento; comparar
   inventário com arquivos originais e verificar páginas ilegíveis/OCR.
3. Registrar data de referência, cobertura e limitações; identificar peças no
   PDF quando necessário. Ausência de segundo grau só pode ser declarada quando
   o advogado a verificou. Acervo enviado não equivale a autos completos do tribunal.
4. Informar perguntas e preparar análise das evidências. Abrir as fontes dos
   fatos relevantes, conferir citações, registrar pendências para documentos
   ausentes e registrar a conferência das evidências.
5. Gerar minuta para revisão. Conferir se utiliza os documentos e a comunicação
   atual, admite lacunas e não cria fatos/citações. Editar o texto e registrar a
   revisão humana. Recarregar a página durante uma operação para verificar retomada.
6. Conferir auditoria e vínculo entre caso, prazo, arquivos e minuta. Nenhuma
   etapa deste roteiro autoriza protocolar uma peça no tribunal.

## Registro do resultado

| Item | Evidência do caso |
| --- | --- |
| Ambiente / versão / data | Preencher após implantação e login |
| Caso e autorização | Identificador interno, sem dados pessoais neste documento |
| Revisor | Identificador interno |
| Publicação ou demanda | Origem e data |
| Prazo | Data conferida e ressalvas de calendário |
| Acervo | Quantidade de arquivos/páginas e lacunas |
| Fontes | Citações verificadas e divergências |
| Minuta | Correções exigidas pelo revisor |
| Tempo | Comparação com execução habitual |
| Resultado | Aprovado para piloto / corrigir / impedido |

Testes automatizados e providers simulados são evidência técnica. Viabilidade
do primeiro piloto depende deste registro real, com julgamento do advogado.
