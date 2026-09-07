# Roteiro de evolução — Simulador Planeta 9 (pós-Auditoria V3)

Este documento organiza o que vem depois de fechar P0-1/P1-2/P1-3/P2-4, em
horizontes. Não é uma lista de tarefas para eu executar agora — é o mapa para
você priorizar, sessão por sessão, trazendo o contexto que precisar em cada
uma.

---

## Horizonte 0 — em andamento, não repetir
Fechamento da Auditoria V3 (P0-1 reescrita do artigo, P1-2, P1-3, P2-4),
rodando em sessão separada agora. Só volta a este roteiro depois de fechado.

---

## Horizonte 1 — decisões estruturais que bloqueiam o resto

Estas quatro coisas não são "features novas" — são lacunas que, se ficarem
abertas, tornam qualquer trabalho depois delas retrabalho.

**1.1 — Fase B: ω9/Ω9/M0 fixos ou variando por linha do Quadro 2**
Hoje as 7 linhas usam os mesmos ângulos (200°/270°/180°) por decisão
pragmática, mas isso está registrado como aberto desde a Fase A. Se a
resposta for "cada configuração deveria ter seus próprios ângulos" (mais
correto fisicamente, já que M/a/e/i diferentes deveriam ter geometria
orbital própria testada), isso muda os dados de entrada de 6 das 7 linhas
e invalida comparações diretas com o que já foi rodado. Decidir isso ANTES
de investir em rodar mais candidatos evita rodar tudo duas vezes.

**1.2 — Remedir `hardware_benchmark.json` na máquina real (item B2 já
identificado)**
Bloqueia qualquer estimativa confiável de quanto tempo custa rodar o
Quadro 2 completo em escala secular. Sem isso, qualquer decisão sobre
"vale a pena rodar 1e8 vs 1e9 vs 4e9 anos" é feita no escuro.

**1.3 — Cruzamento externo dos 13 ETNOs com a Tabela A1
(De la Fuente Marcos & De la Fuente Marcos 2014, arXiv:1406.0715)**
Nunca foi feito campo a campo. É trabalho de verificação, não de código —
baixo custo, mas fecha uma lacuna de proveniência de dados que uma banca
pode perguntar diretamente.

**1.4 — Estratégia de versionamento (`runs/` + `.gitignore`)**
Antes do repositório crescer com mais runs reais, decidir o que entra no
histórico git (as runs em si? só os manifests/resumos? nada?) evita um
repositório poluído com artefatos grandes ou, pior, perda de proveniência
por estar fora do controle de versão.

---

## Horizonte 2 — a decisão mais cara: rodar de verdade em escala secular

Isto é o núcleo científico do projeto e a decisão de maior impacto/custo.
Só faz sentido depois do Horizonte 1 estar fechado (senão você paga o custo
de compute e ainda pode ter que refazer por causa de 1.1).

- Rodar as 7 configurações do Quadro 2 com `secular.yaml` (1e8 anos hoje) —
  ou o horizonte que 1.2 mostrar ser viável.
- Critério de sucesso: cada linha da Tabela 2 do artigo passa a ter um
  `run_manifest.json` real por trás, não uma reescrita honesta "não
  executado ainda".
- Este é o ponto onde o prazo da FEBRACE decide a estratégia: se o prazo é
  curto, a versão "artigo honesto sobre o que foi 1 Myr, com Gyr como
  trabalho futuro declarado" (o que está sendo feito agora) pode ser o
  entregável final por necessidade, não por escolha — o que é uma posição
  cientificamente defensável para uma banca, desde que assumida
  explicitamente. Se há mais tempo, este horizonte vira o objetivo real
  antes da versão final do artigo.

---

## Horizonte 3 — completar o funil (estágios 4 e 5, hoje `not_implemented`)

O próprio `montecarlo.py` já declara honestamente que faltam:
- **Estágio 4** — filtro de Hamiltoniano secular (formalismo tipo
  Batygin & Morbidelli 2017), que precisaria de um modelo de ângulo
  ressonante que hoje não existe no código.
- **Estágio 5** — detectabilidade IR/óptica (modelo fotométrico
  albedo/raio → magnitude aparente + dados reais de profundidade/cobertura
  de survey), que também não existe.

Ambos são trabalho substancial (não é "adicionar uma função") e dependem de
decisão de escopo: vale a pena implementar antes da FEBRACE, ou "marcado
como not_implemented, discutido como trabalho futuro" é uma posição honesta
e aceitável para a banca? Isso é uma pergunta sua, não uma que eu decida.

---

## Horizonte 4 — ampliação metodológica opcional (mais risco/retorno)

**4.1 — Surrogate de ML para o estágio 1.5 do funil** (já discutido:
acelerar a triagem entre estágio 1 e 2/3, no estilo SPOCK/Tamayo et al.
2020). Só faz sentido depois que houver volume real de dados do estágio 2/3
(ou seja, depois do Horizonte 2), porque sem dados de treino reais não há o
que aprender. Não é prioridade agora — fica registrado aqui para quando o
funil já estiver gerando dados em escala.

**4.2 — Modelos nulos / significância estatística mais robusta** — vale
revisar se `shuffle_varpi` (ou equivalente) já cobre isso de forma
suficiente para as alegações que o artigo final vai fazer, uma vez que o
Horizonte 2 gerar resultados reais para testar.

---

## Horizonte 5 — fechamento para submissão

- Consolidar `docs/historico/CHANGELOG_V3.md` e um `RELATORIO_EVOLUCAO_V3.md`
  no mesmo padrão do `RELATORIO_EVOLUCAO_POS_V2.md` existente.
- Atualizar `docs/LIMITACOES.md` para refletir o estado final antes da
  submissão — a lista de limitações declaradas é, por si só, parte do que
  torna o artigo defensável perante a banca.
- Revisão de formatação ABNT do artigo (separado do conteúdo científico).

---

## O que eu preciso saber para ajudar a priorizar isso

- **Prazo da FEBRACE**: isso muda tudo — se o Horizonte 2 (rodar de verdade
  em escala secular) é realista antes da submissão ou se o artigo final vai
  ser necessariamente a versão "honesto sobre 1 Myr, Gyr como trabalho
  futuro".
- **Quem decide 1.1 (Fase B)**: se é uma decisão sua ou se depende de
  orientador/banca — porque ela redefine dado de entrada de 6 candidatos.
- Nada disso precisa de resposta agora — é só o que eu vou perguntar quando
  a conversa chegar em cada horizonte, se você trouxer o assunto de volta.
