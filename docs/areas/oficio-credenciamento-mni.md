# Ofício de credenciamento MNI — modelo para preencher

Modelo pronto para envio à DTI do tribunal. Substitua os campos `«ASSIM»` e
apague esta seção de instruções antes de protocolar.

**Antes de enviar:**

1. **Procure o formulário próprio do tribunal primeiro.** Vários tribunais têm
   processo específico para "acesso automatizado por sistemas externos" — usá-lo
   é mais rápido do que ofício genérico. Este modelo serve quando não houver.
2. **Escolha o tribunal** cruzando dois critérios (ver
   [`mni-credenciamento.md`](mni-credenciamento.md#22-escolha-do-tribunal-do-piloto)):
   onde o advogado do piloto tem processos ativos, e de preferência entre os que
   já têm endpoint confirmado (TJPE, TJPI, TJAP, TRF5, TRF6).
3. **Confirme o Provimento local.** O item citado abaixo (355/2018) é do TJMG.
   Cada tribunal tem o seu Código de Normas — troque pelo do tribunal-alvo ou
   suprima a menção.
4. As **6 perguntas** da seção III não são acessórias: as respostas 2, 5 e 6
   definem o desenho do protocolo via MNI. Não corte essa seção.

---

OFÍCIO Nº «NUMERO»/«ANO»

«CIDADE/UF», «DIA» de «MÊS» de «ANO».

À Diretoria de Tecnologia da Informação do «TRIBUNAL»
«ENDEREÇO OU E-MAIL DE PROTOCOLO»

**Assunto:** Solicitação de credenciamento para acesso ao webservice do Modelo
Nacional de Interoperabilidade (MNI), versão 2.2.2.

Senhor(a) Diretor(a),

**I — Da qualificação e do objeto**

1. «NOME COMPLETO DO ADVOGADO», inscrito(a) na Ordem dos Advogados do Brasil,
Seccional «UF», sob o nº «NÚMERO OAB», CPF nº «CPF», com escritório em
«ENDEREÇO», vem respeitosamente requerer **credenciamento para acesso ao
webservice do Modelo Nacional de Interoperabilidade (MNI)**, na versão 2.2.2,
mantido por este Egrégio Tribunal.

2. O acesso destina-se ao uso do sistema **Causor**, ferramenta de automação do
acompanhamento processual e do peticionamento utilizada pelo próprio requerente,
**restrita aos processos em que atua como patrono constituído**. Não se pretende
acesso a acervo geral, consulta de terceiros, nem coleta massiva de dados.

**II — Do fundamento**

3. A **Resolução Conjunta CNJ/CNMP nº 3/2013** institui o Modelo Nacional de
Interoperabilidade como padrão de intercâmbio de informações de processos
judiciais entre os órgãos do Poder Judiciário e demais instituições, por meio de
webservice.

4. O **«PROVIMENTO/CÓDIGO DE NORMAS LOCAL — ex.: Provimento 355/2018 no TJMG»**
disciplina, no âmbito deste Tribunal, o acesso por essa via.

5. A **Lei nº 11.419/2006, art. 1º, §2º, III**, reconhece como assinatura
eletrônica válida aquela decorrente de **cadastro de usuário no Poder
Judiciário**, hipótese que se pretende ver esclarecida no item III.5 abaixo.

**III — Do que se requer**

6. Requer-se o credenciamento para as seguintes operações do MNI 2.2.2:

   a) **`consultarProcesso`**, com o parâmetro `incluirDocumentos = true`, para
      leitura íntegra dos autos dos processos em que o requerente atua;

   b) **`entregarManifestacaoProcessual`**, para protocolo de petições nesses
      mesmos processos.

7. Requer-se, ainda, **acesso a ambiente de homologação** previamente à
produção, caso este Tribunal o disponibilize.

8. Para viabilizar a integração em conformidade com as normas deste Tribunal,
solicita-se a gentileza de esclarecer:

   1. Qual a **URL exata** do endpoint MNI de 1º e 2º graus, em produção e em
      homologação?
   2. A autenticação se dá por **usuário e senha** (`idConsultante` /
      `senhaConsultante`) ou exige **certificado digital ICP-Brasil no canal**
      (autenticação mútua TLS)?
   3. A operação `consultarProcesso` com `incluirDocumentos = true` retorna o
      **teor** (conteúdo binário) dos documentos, ou apenas seus metadados?
   4. Há **limite de requisições**, janela de horário ou política de uso a
      observar?
   5. O protocolo via `entregarManifestacaoProcessual` **dispensa a assinatura
      por certificado digital**, nos termos do art. 1º, §2º, III, da Lei
      11.419/2006, considerando-se o próprio credenciamento como assinatura
      eletrônica?
   6. A resposta da operação de entrega retorna **número e comprovante de
      protocolo**?

**IV — Dos compromissos**

9. O requerente compromete-se a: (a) limitar o acesso aos processos em que
figure como patrono constituído; (b) observar a Lei nº 13.709/2018 (LGPD) e o
sigilo legal aplicável, inclusive quanto a processos em segredo de justiça;
(c) armazenar as credenciais fornecidas de forma cifrada e de acesso restrito;
(d) respeitar os limites de uso definidos por este Tribunal; e (e) comunicar
imediatamente qualquer incidente de segurança.

10. Nestes termos, pede deferimento.

Atenciosamente,

_______________________________________
**«NOME COMPLETO DO ADVOGADO»**
OAB/«UF» nº «NÚMERO»
«E-MAIL» · «TELEFONE»

---

## Depois do deferimento

O passo a passo de cadastro e validação está em
[`mni-credenciamento.md`](mni-credenciamento.md#26-depois-do-deferimento).
Em resumo: cadastrar a credencial em Configurações → Acesso aos tribunais,
corrigir o endpoint em `connectors/mni/profiles.py` se a URL informada divergir
da tabela, e rodar `RUN_MNI_LIVE=1`.
