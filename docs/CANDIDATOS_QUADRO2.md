# Candidatos do Quadro 2 (data/candidates_quadro2.csv)

Este arquivo documenta, linha a linha, quais valores vêm do artigo
(Quadro 2 — Configurações avaliadas na simulação N-corpos, Seção 4) e
quais foram assumidos por ausência de dado, para que a origem de cada
número seja auditável e o artigo não apresente suposição como medição.

## Regra de preenchimento

O artigo não especifica i9 para as linhas 1, 2, 3 e 5, nem M9 para a
linha 3. Em vez de escolher um valor central arbitrário e diferente
por linha (o que introduziria uma variável de confusão extra e não
controlada em cada comparação), todo valor ausente foi fixado no
mesmo baseline: o do Cenário 6 (M=6, a=500, e=0,35, i=20°) — o
"Cenário intermediário (preferido)" da Seção 8.2, único explicitamente
rotulado como referência no artigo. Isso isola, em cada linha, apenas
a(s) variável(is) que o Quadro 2 realmente testa, em vez de somar um
segundo grau de liberdade não testado.

Os ângulos ω9=200°, Ω9=270°, M0=180° são um ponto central único,
aplicado a todos os candidatos (não vêm do Quadro 2, que não tabula
esses três ângulos). O artigo (Seção 9) só restringe Ω9 qualitativamente
(hemisfério sul celeste, |b|>20°) e M0 qualitativamente (próximo ao
afélio); não há intervalo numérico para ω9 no texto.

**Decisão Horizonte 1.1 (fechada em 2026-08-16):** manter ω9/Ω9/M0 fixos
e iguais para todas as 7 linhas (Opção 1 do PROMPT_EXECUCAO_PLANET9).
Razão: não há run secular real ainda, e o objetivo atual é sensibilidade
conservadora do screening, não robustez fina por linha. Variar por linha
(Opção 2a, sweep real; Opção 2b, valores da literatura sem medir) fica
condicionado a uma futura decisão de rodar o Horizonte 2 (run secular) —
não faz sentido pagar o custo de compute de 2a antes disso, e 2b não
adiciona evidência, só narrativa. Única linha com cobertura angular real
é `p9_row6_preferred` (run `angle_robustness`, 5 valores de ω9, todos
`candidate_of_interest`); as outras 6 seguem sem evidência de robustez a
ω9 — isso é uma limitação registrada, não um problema resolvido.

## Linha a linha

| candidate_id | Do artigo (Quadro 2) | Assumido (não está no artigo) |
|---|---|---|
| p9_row1_lowmass_close | M=4, a=300, e=0,20 | i=20° (baseline linha 6) |
| p9_row2_highmass_close | M=10, a=300, e=0,50 | i=20° (baseline linha 6) |
| p9_row3_far_eccentric | a=800, e=0,60 | M=6, i=20° (baseline linha 6) |
| p9_row4_incl_boundary | — (linha 4 é regra de corte "i > 30°", não um ponto) | M=6, a=500, e=0,35 (baseline linha 6); i=32° como sonda única 2° acima do corte declarado, teste de sensibilidade de fronteira, não uma varredura completa |
| p9_row5_partial_alignment | M=5, a=400, e=0,30 | i=20° (baseline linha 6) |
| p9_row6_preferred | M=6, a=500, e=0,35, i=20° | (nenhum — linha completa no artigo) |
| p9_row7_highmass_viable | M=7, a=600, e=0,45, i=18° | (nenhum — linha completa no artigo) |
| p9_row8_bb21_bestfit | M=6,2, a=382,4, e=0,20, i=15,6° (Brown & Batygin 2021, AJ 162, 219, posterior/melhor ajuste, citado em Chen et al. 2025) | ω9=246,7°, Ω9=0° — decomposição escolhida para reproduzir ϖ9=ω9+Ω9=246,7° (BB21); M0=180° mantido igual às outras 7 linhas por ausência de dado melhor |

Todas as linhas 1–7: ω9=200°, Ω9=270°, M0=180° — assumidos, ver acima. A linha 8 (p9_row8_bb21_bestfit) é a exceção documentada na nota abaixo.

A decomposição ω9=246,7°/Ω9=0° foi escolhida por simplicidade (Ω9=0 isola toda a diferença de ϖ9 em ω9); como ω9 e Ω9 afetam o clustering nodal de forma diferente entre si mesmo quando a soma é igual, essa é uma escolha de modelagem documentada, não a única decomposição possível — se o resultado for sensível a essa escolha, isso deve ser testado como extensão futura (sweep de Ω9 mantendo ϖ9 fixo).

## Pendências

- Confirmar ou substituir os valores assumidos de i9 (linhas 1, 2, 3, 5)
  e M9 (linha 3) se houver fonte melhor (rascunho anterior, cálculo de
  inversão gravitacional específico por linha) — hoje é reprodutível e
  documentado, não medido.
- ~~ω9/Ω9/M0 fixos e iguais para todos os candidatos~~ — DECIDIDO em
  2026-08-16 (ver acima). Reabrir apenas se/quando o Horizonte 2 (run
  secular real) for autorizado, não antes.
- p9_row4_incl_boundary usa um único ponto de sonda (i=32°). Se o artigo
  precisar caracterizar onde exatamente o alinhamento quebra, isso vira
  uma varredura de i (ex. 28°, 30°, 32°, 35°) — decisão de escopo
  científico, não técnica, e consome mais do orçamento de
  `max_candidates` em `configs/budgets/secular.yaml` (hoje 8).

## Atualização: catálogo de ETNOs validado (data/etnos/etnos/catalog_validated.csv)

O catálogo default (`data/etnos/catalog.csv`) tinha 4 objetos marcados
`partial`/`example_fixture` — não validados, e por isso o pipeline sempre
emitia o blocker `etno_catalog_not_fully_validated`.

Substituído (via `--etnos data/etnos/catalog_validated.csv`, sem tocar no
arquivo default que os testes usam) por 13 ETNOs reais (a>150 UA, q>30 UA),
com elementos orbitais completos, mesma época, de uma única fonte revisada
por pares: DE LA FUENTE MARCOS; DE LA FUENTE MARCOS (2014), MNRAS Letters
(arXiv:1406.0715), Tabela A1 — que por sua vez cita o JPL Small-Body
Database como origem dos elementos. Anomalia média calculada a partir de
λ e ϖ tabulados pelo artigo (M = λ − ϖ mod 360°), não fornecida diretamente
pela fonte.

Atualização 2026-08-28: uma 14ª linha foi adicionada, o sednoide
`Ammonite_2023_KQ14` (CHEN et al. 2025, Nature Astronomy), o ETNO mais
recente e cientificamente relevante para a hipótese P9 — sua órbita não se
alinha ao agrupamento, o que a literatura cita como evidência que enfraquece
(sem refutar) o cenário de alinhamento simples. `validation_status: partial`
porque a fonte tabula elementos baricêntricos em época 2025-05-05, diferente
do padrão heliocêntrico/época-2014 dos outros 13; ver nota completa na linha
do CSV e em `docs/LIMITACOES.md`.

Atualização 2026-09-03: o catálogo foi ampliado para **16 ETNOs** — as contagens
13 e 14 acima são marcos históricos, não o estado atual. Duas linhas reais foram
adicionadas com `validation_status: partial` (mesmo caveat de época/frame
baricêntricos do Ammonite, sem propagação para época comum): `2017_OF201`
(Cheng, Li & Yang 2025, arXiv:2505.15806) — desafia o agrupamento (ϖ=306,9°,
fora do clustering clássico perto de ϖ~60°); e `Leleakuhonua_2015_TG387`
("The Goblin"; Sheppard, Trujillo & Tholen 2019, AJ 157, 139) — consistente
com o agrupamento (a descoberta simula pastoreio por P9 e encontra comportamento
estável similar ao dos ETNOs já alinhados). Detalhe completo por linha nos
`selection_notes` de cada linha do CSV e em `docs/LIMITACOES.md`.

Confirmado rodando `screen` real com os dois catálogos novos: o blocker de
catálogo não validado desaparece; resta só `no_observational_bias_model`,
que é uma limitação diferente (ainda real, não uma opção nova a decidir
agora).

Referência já adicionada em ordem alfabética na seção REFERÊNCIAS do
`docs/Artigo_FEBRACE_revisado.docx`.

## Atualização: candidato BB21 rodado (sanidade, 2026-09-03)

p9_row8_bb21_bestfit foi executado com sucesso no pipeline real (REBOUND, orçamento
`medium.yaml`, 200 anos, 8 candidatos, `catalog_validated.csv`): status `completed`,
rank 1, classificação `candidate_of_interest`, `evidence_level: weak` (mesma política
de evidência que já limita todos os outros candidatos — ver conclusion_policy.yaml).
Blockers ativos: `no_observational_bias_model` (Ponto 5 do plano pós-auditoria, ainda
pendente), `etno_catalog_not_fully_validated` (o catálogo inclui Ammonite_2023_KQ14,
`validation_status: partial`).

**Isto é uma checagem de sanidade, não o resultado final do artigo:** o horizonte
foi de 200 anos (orçamento `medium`), não a escala secular de 4 Gyr que o
`secular.yaml` define como alvo para validação de estabilidade. Nenhum dos 8
rankings muda o fato de que a evidência é `weak` e a comparação com
`p9_row6_preferred` (que também é `candidate_of_interest`) requer uma run
conjunta no orçamento secular — não pode ser inferida desta run curta (mesmo
com o BB21 em rank 1, o `delta_dynamic_score` de 0.151691 versus 0.110427 das
outras linhas é uma medida preliminar de 200 anos, não uma declaração de que o
BB21 é "melhor" que os demais candidatos do Quadro 2).

Itens de robustez V2 (leave-one-out, propagação de incerteza, modelos nulos,
convergência, detectabilidade) não foram executados para este candidato: `not_run`.

**Atualização 2026-09-03 — checagem de viés de seleção disponível:** ver
`docs/LIMITACOES.md` para o resultado completo do módulo
`selection_bias.py` (ponto 5 do plano pós-auditoria). Resultado resumido:
R_real (0,30) > R_sintético_sob_seleção (0,01) para o catálogo de 16
ETNOs — não confirma nem descarta viés de seleção com força, apenas não
reproduz o clustering com um modelo simplificado de 3 fatores.
