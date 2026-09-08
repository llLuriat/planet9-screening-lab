# Limitações

Este projeto não confirma a existência do Planeta 9.

Este projeto não determina a órbita real do Planeta 9.

## Atualização V2 (item 1 do plano V1->V2: horizonte secular)

O que passou a existir de verdade nesta revisão:

- `configs/budgets/secular.yaml`: horizonte de integração em escala Myr (1e8 anos
  como ponto de partida conservador; NÃO 4e9 ainda - ver abaixo) com timestep
  derivado fisicamente do período orbital de Júpiter (`P/20`), não um número
  chutado. A derivação é feita em código
  (`planet9lab.physics.recommended_timestep_years`) e um teste garante que o
  YAML não pode divergir silenciosamente dela.
- Checkpointing real: `ReboundEngine.run_branch_checkpointed` salva o estado
  completo da simulação (REBOUND Simulationarchive) e séries de ΔE/E0, ΔL/L0 e
  Δϖ em CSV a cada `checkpoint_interval_years`, e retoma do último checkpoint
  em vez de reiniciar do zero. `resume_run` deixou de ser um stub que só
  reportava status: ele agora recomputa somente os candidatos ainda
  pendentes, usando os checkpoints de engine já salvos.
- Critério quantitativo de "Δϖ estável" (`planet9lab.metrics.delta_pomega_stability`):
  estatística circular (resultant length R) sobre a segunda metade da série
  temporal de cada ETNO, com o threshold documentado no código, não escondido
  em prosa.

O que ainda NÃO está resolvido e precisa ser honesto no artigo:

- **`integration_years: 1e8` em `secular.yaml` ainda não foi validado contra o
  hardware real que vai rodar o pipeline.** `scripts/benchmark_integration_cost.py`
  existe para medir isso (tempo de parede real por candidato) e, desde a Etapa
  3 (2026-08-15), grava proveniência explícita no JSON (`cpu_model`,
  `logical_cpus`, `physical_cores`, `hardware_platform`, `measured_on` e uma
  nota de que o número vale só para a máquina que o gerou). Foi executado no
  ambiente sandbox (Intel Xeon @ 2.50 GHz, 2 núcleos) e o resultado está em
  `results/hardware_benchmark.json` — **marcado como medição de sandbox, não
  como referência de prazo do artigo**. O benchmark no hardware real do
  usuário (E3-1230 V2) permanece PENDENTE: rode
  `python scripts/benchmark_integration_cost.py` nessa máquina e commite o JSON
  resultante. Enquanto não existir medição na máquina real, `integration_years`
  é uma escolha conservadora de ponto de partida, não um valor testado. Se ao
  rodar o benchmark 4e9 anos (ou mesmo 1e9) não couber no orçamento de tempo
  disponível, o artigo deve reportar o maior valor efetivamente executado, não
  o valor originalmente pedido.
- ~~Catálogo canônico ainda usa fixtures parciais.~~ RESOLVIDO: o catálogo
  default (`data/etnos/catalog.csv`) segue com 4 fixtures, mas existe
  `data/etnos/catalog_validated.csv` (13 ETNOs reais, a>150 UA, q>30 UA, mesma
  época, fonte revisada por pares - De la Fuente Marcos & De la Fuente Marcos
  2014, Tabela A1) que remove o blocker de catálogo; use
  `screen --etnos data/etnos/catalog_validated.csv`. O catálogo `catalog_v2.csv`
  ainda não foi validado externamente contra MPC/JPL/Horizons (bloqueia).
- Atualização 2026-08-28: `catalog_validated.csv` passou a ter 14 linhas — os
  13 objetos originais de De la Fuente Marcos (2014) mais o sednoide
  `Ammonite_2023_KQ14` (CHEN et al. 2025, Nature Astronomy, doi:10.1038/s41550-025-02595-7),
  `validation_status: partial` (não `validated` como os outros 13) porque seus
  elementos, conforme tabulados pela fonte, são **baricêntricos** e de época
  **2025-05-05**, enquanto os outros 13 são heliocêntricos em época
  2014-05-23 — nunca propagados para uma época comum antes de entrar na
  simulação (o engine usa os elementos osculadores como estão, ignorando o
  campo `epoch`). Ver `selection_notes` da linha no CSV para o detalhe
  completo. Reprocessar via JPL Horizons numa época comum antes de usar este
  objeto para qualquer claim quantitativo (não apenas qualitativo/robustez).

**Atualização 2026-09-03 — catálogo ampliado para 16 ETNOs (ponto 4 do plano
pós-auditoria):** dois objetos reais adicionados a `catalog_validated.csv`,
`validation_status: partial` (mesmo caveat de época/frame do Ammonite):
`2017_OF201` (Cheng, Li & Yang 2025, arXiv:2505.15806) — desafia o agrupamento,
ϖ=306,9° fora do clustering clássico; e `Leleakuhonua_2015_TG387` (Sheppard,
Trujillo & Tholen 2019, AJ 157, 139) — consistente com o agrupamento. Screen
real executado com os 16 ETNOs e 8 candidatos (orçamento `medium`, run
`runs/screen_20260903T211311606520Z`), sem erro numérico. Objetos identificados
mas fora deste lote (sem elementos verificados nesta rodada): 2015 BP519, 2013
FT28, 2015 GT50 — registrados como próximo lote, não implementados.

- ~~Não há modelo completo de viés observacional.~~ PARCIAL: um modelo de viés
  de *seleção* observacional foi implementado em duas versões —
  **Atualização 2026-09-03** (angle-only, 3 fatores uniformes,
  `bias_model: none`) e **Atualização 2026-09-07** (`bias_model:
  h_prior_from_catalog`, fator de profundidade por objeto via magnitudes H
  do JPL SBDB, catálogo `data/etnos/h_values.csv`). Um modelo de viés
  observacional *completo* continua inexistente.
- ~~Leave-one-out não é executado.~~ RESOLVIDO: implementado
  (`python main.py leave-one-out --from-run <run> --top N`); as duas runs reais
  ainda não o executaram (`leave_one_out_status: not_run`).
- Propagação de incerteza não é executada (`uncertainty_propagation_status`).
- ~~Modelos nulos extras (além do controle com/sem P9) não são executados.~~
  RESOLVIDO: implementados (`python main.py null-models --models
  shuffle_varpi,randomize_angles,no_p9_catalog_baseline`); as duas runs reais
  ainda não os executaram.
- Detectabilidade (limites IR/óptico) não é executada (`detectability_status`).
- ~~MCMC/Monte Carlo real sobre `[M9, a9, e9, i9]` ainda não existe (item 2 do
  plano V1->V2 - próximo bloco a implementar).~~ PARCIAL: amostragem QMC
  (sequência de Halton) sobre `[M9, a9, e9, i9]` existe (`montecarlo.py`,
  estágios 0-3); MCMC real ainda não existe.
- Candidatos do Quadro 2 do artigo existem e estão documentados linha a linha
  em `data/candidates_quadro2.csv` + `docs/CANDIDATOS_QUADRO2.md` (8 linhas,
  com origem de cada valor e quais foram assumidos). O catálogo padrão do
  `screen` (`data/candidates_example.csv`) ainda é o conjunto de exemplo mais
  barato; use `screen --candidates data/candidates_quadro2.csv` com
  `configs/budgets/secular.yaml` (`max_candidates: 8` = exatamente os 8 reais)
  para rodar o Quadro 2 completo.
- O candidato `p9_row8_bb21_bestfit` (Brown & Batygin 2021, AJ 162, 219,
  posterior/melhor ajuste: M=6,2, a=382,4 UA, e=0,20, i=15,6°) foi adicionado ao
  Quadro 2 (8ª linha) e rodado apenas em orçamento curto de sanidade
  (`medium.yaml`, 200 anos, 2026-09-03): `completed`, rank 1,
  `candidate_of_interest`, `evidence_level: weak`, blockers
  `no_observational_bias_model` + `etno_catalog_not_fully_validated`. A escala
  secular (`secular.yaml`, 4 Gyr) e os itens de robustez V2 (leave-one-out,
  propagação de incerteza, modelos nulos, convergência, detectabilidade)
  permanecem `not_run` para este candidato — ver `docs/CANDIDATOS_QUADRO2.md`.
- Rastreabilidade artigo<->run (`article_section_ref`, `export_to_article.py`)
  ainda não existe (item 4). Confirmado ausente no código em 2026-08-15.

**Atualização 2026-09-03 — modelo de viés observacional implementado (ponto 5 do
plano pós-auditoria, versão inicial):** planet9lab/selection_bias.py e o
comando selection-bias-check --from-run <run> comparam a concentração
angular (ϖ = ω + Ω, estatística R tipo Rayleigh) do catálogo real de 16 ETNOs
contra uma população sintética uniforme submetida a um modelo de seleção de 3
fatores (profundidade limitante em V, cobertura de céu, arco mínimo de
rastreamento — desenho de Napier et al. 2021, arXiv:2102.05601, Seção 3).

**Atualização 2026-09-07 — modelo com H-prior do SBDB
(ias_model: h_prior_from_catalog):** o fator de profundidade agora é
calculado **por objeto** a partir de sua magnitude absoluta H. Cada objeto
sintético sorteia um H do catálogo empírico data/etnos/h_values.csv
(16 valores do JPL Small-Body Database, consultados 2026-09-07 —
data/etnos/h_values_attribution.md lista cada valor com ref SBDB). A
sobrevivência à profundidade usa _depth_prob_from_h(h, V_lim): objetos
mais fracos que a mediano (H=6.5) são penalizados linearmente (−0,12 por
magnitude); objetos mais brilhantes NÃO são boostados (conservativo). O
catálogo abrange de Sedna (H=1,50) a objetos em H~8,5, cobrindo a faixa
real da amostra. Albedo assumido: 0,10 (Sheppard & Trujillo 2016,
AJ 152:221) para estimativa de diâmetro — marcado como TODO substituir
por V = H + 5 log10(r·Delta) quando a população sintética passar a
carregar distância heliocêntrica.

**Atualização 2026-09-07 (2ª etapa) — modelo com curva OSSOS de eficiência de
detecção (ias_model: h_prior_from_catalog + ossos_efficiency_params):**
o fator de profundidade agora usa a curva quadrática-logística de Bannister
et al. 2018 (ApJS 236:18, arXiv:1805.11740, §5.2), η(m) = (eff_max − c·(m−21)²)
/ (1 + exp((m−m₀)/σ)), avaliada na magnitude aparente real V = H + 5 log10(r·Δ)
de cada objeto sintético. Os parâmetros padrão (eff_max=0,8877, c=0,02763,
m₀=24,142, σ=0,1537) são a média dos três blocos 2013AE do OSSOS
(data/etnos/ossos_efficiency_attribution.md documenta a derivação). A
população sintética agora carrega distâncias heliocêntrica (r) e geocêntrica
(Δ) sorteadas de uma prior de q = a(1−e) do catálogo real, coerente com os
elementos orbitais simulados. O albedo permanece fixo em 0,10 (Sheppard &
Trujillo 2016).

**Limitações que impedem tratar isto como confirmação forte (reportar
sempre junto com o resultado acima, nunca isolado):**

- O modelo continua *angle-only*: profundidade e arco de rastreamento são
  penalidades independentes dos ângulos do objeto — apenas o fator de
  cobertura de céu tem dependência angular. Capacidade limitada de gerar
  clustering artificial; o teste é melhor lido como `este modelo
  simplificado específico não explica o clustering`, não como `não há
  viés de seleção`.
- A magnitude aparente V = H + 5 log10(r·Δ) não inclui função de fase
  (V = H + 5log10(r·Δ) − 2.5log10(φ(α))) — a população sintética não carrega
  ângulo de fase α. TODO marcado no código.
- A curva OSSOS é válida para magnitudes r ~21–25 e taxas no plano do céu
  0,50–8,00 arcsec/hora; fora dessas faixas a eficiência reportada é
  extrapolação.
- A cobertura de céu usa o **filling factor médio publicado do OSSOS**
  (0,9067 = média aritmética de 0,9079 [bloco 2013A-E] e 0,9055
  [bloco 2013A-O], Bannister et al. 2016a) como probabilidade de aceitação
  posicional uniforme — substitui a aproximação antiga `sky_coverage_deg2/41253`.
  Como a população sintética é angle-only (sem posição no céu para testar
  contra os polígonos de footprint reais), **não há filtragem posicional
  real por bloco**; próximo passo: projeção orbital → posição angular +
  teste point-in-polygon contra `data/ossos_2013a_blocks.py`.
- Não modela cadência real (DES, OSSOS, etc.).
- O resultado não deve ser citado como probabilidade de detecção calibrada.
- `selection-bias-check` desativa o blocker antigo
  `no_observational_bias_model` (`blocker_if_none: false` na config
  atual) em resultado favorável; em resultado desfavorável adiciona
  `selection_bias_not_ruled_out`.
- `apply_v2_evidence` capa o nível de evidência em `weak` quando
  `real_exceeds_synthetic_R: false`; quando `true`, NÃO eleva
  automaticamente — o teste passar é necessário, não suficiente, para
  qualquer nível acima de `weak`.

Próximos passos possíveis (fora do escopo deste lote): modelo de
seleção dependente de magnitude aparente real com função de fase
(requer ângulo de fase α sintético) e footprint geométrico real de survey.

## Atualização V2 (item 2 do plano V1->V2: Monte Carlo / QMC)

O que passou a existir de verdade:

- `planet9lab/montecarlo.py`: amostragem QMC (sequência de Halton, determinística)
  ou uniforme pseudoaleatória sobre `[M9, a9, e9, i9]`, com limites de
  `configs/montecarlo/parameter_space.yaml` justificados na literatura
  (Brown & Batygin 2016/2021) e comentados no próprio YAML.
- Funil real em 4 estágios computados (não hardcoded):
  1. `stage0_physical_bounds` - checagem analítica, grátis, todos os N pontos.
  2. `stage1_hill_separation_proxy` - critério analítico de separação de Hill
     em relação a Netuno, grátis, todos os N pontos.
  3. `stage2_gross_stability` - integração REBOUND curta (1e6 anos,
     `configs/budgets/montecarlo_stage2.yaml`), aplicada só aos sobreviventes
     do estágio 1, **limitada por `max_stage2_samples`** por custo
     computacional (excesso marcado `not_evaluated_capacity_limit`, nunca
     descartado silenciosamente).
  4. `stage3_apsidal_alignment` - integração completa em escala secular
     (`configs/budgets/secular.yaml`, com checkpointing) contra o catálogo
     real de ETNOs, aplicada só aos sobreviventes do estágio 2, também
     limitada por `max_stage3_samples`.
- `results/parameter_space_scan.csv` com uma coluna booleana por filtro
  (auditável) e `results/reduction_funnel_summary.json` com os percentuais
  calculados diretamente da contagem de pontos.
- Comando novo: `python main.py montecarlo-scan --config
  configs/montecarlo/parameter_space.yaml --seed <N>`.

O que ainda NÃO está implementado, marcado explicitamente como
`not_implemented` no `reduction_funnel_summary.json` (não embutido em prosa):

- `stage4_secular_hamiltonian`: precisaria de um modelo de Hamiltoniano
  secular / ângulo ressonante (ex. formalismo de Batygin & Morbidelli 2017),
  que não existe neste código.
- `stage5_detectability_ir_optical`: precisaria de um modelo fotométrico
  (albedo/raio assumidos -> magnitude aparente) e dados reais de
  profundidade/cobertura de surveys - o mesmo gap rastreado como
  `detectability_status` no item 5 do plano.

**Custo computacional ainda não validado em hardware real.** Os valores padrão
de `max_stage2_samples` (200) e `max_stage3_samples` (60) em
`configs/montecarlo/parameter_space.yaml` são pontos de partida conservadores,
não valores medidos no seu E3-1230 v2. Rode
`scripts/benchmark_integration_cost.py` primeiro; se o tempo por candidato do
estágio 3 for muito alto, reduza `max_stage3_samples` antes de rodar o scan
completo com `n_points: 20000`, ou o comando pode ficar rodando por dias sem
terminar o estágio 3.



Havia um pacote local `pytest/` na raiz do projeto que **sombreava** qualquer
`pytest` real instalado (Python prioriza o diretório atual do projeto sobre
`site-packages` ao rodar `python -m pytest`). Isso foi corrigido: o shim foi
movido para `scripts/offline_pytest_shim/` e só é alcançável por invocação
explícita. Rode sempre `pip install -e .[dev]` (ou `pip install pytest
pydantic rebound ...`) e `python -m pytest` a partir da raiz do projeto para
ter certeza de que está usando o pytest real, com suporte a fixtures,
`monkeypatch` e `pytest.approx` - vários testes novos (checkpointing, resume)
dependem disso e falham ao importar sob o shim antigo (isso é esperado e
intencional: falhar explicitamente é melhor do que rodar silenciosamente uma
versão mais fraca do test runner).

O maior claim permitido continua conservador e condicionado ao protocolo. Sem
modelo de viés observacional, a evidência máxima continua limitada a `weak`.

## Atualização V2 (item 5 do plano V1->V2: fusão da branch de robustez)

Uma sessão paralela implementou os itens de robustez do plano (item 5)
enquanto esta trabalhava no horizonte secular e no Monte Carlo (itens 1-2).
As duas linhas de trabalho foram fundidas manualmente após uma auditoria
completa arquivo por arquivo - não houve substituição silenciosa. Detalhes
completos em `docs/historico/CHANGELOG_V2.md`.

O que passou a existir de verdade (não estava disponível nas seções acima):

- **Leave-one-out** (`python main.py leave-one-out --from-run <run> --top N`):
  re-roda cada candidato do top N removendo um ETNO de cada vez, gera
  `robustness_score` por candidato.
- **Convergência numérica** (`python main.py convergence ...`): testa
  estabilidade do delta_dynamic_score sob refinamento de timestep (dt, dt/2, dt/4).
- **Validação IAS15** (`python main.py validate-top --integrator ias15`):
  confirma que o sinal do delta não depende do integrador (WHFast vs IAS15).
- **Modelos nulos reais** (`python main.py null-models --models
  shuffle_varpi,randomize_angles,no_p9_catalog_baseline`): compara o delta
  real contra distribuições nulas geradas por REBOUND de verdade (não é
  estatística analítica aproximada). Usa sub-orçamento configurável
  (`null_model_integration_years`) para manter o custo computacional viável,
  documentado e auditável, nunca reduzido silenciosamente.
- **Diagnósticos** (`diagnose-scoring`, `diagnose-null-models`): explicam
  quais componentes do score saturam e por que os modelos nulos passam/falham.
- **Famílias de candidatos** (`candidate-families`): agrupa candidatos
  similares por distância no espaço de parâmetros - diagnóstico, não evidência
  orbital independente.
- **Catálogo V2** (`data/etnos/catalog_v2.csv` + `catalog_sources.md` +
  `catalog_validation_report.md`): mesmos objetos do catálogo V1, mas com
  seleção explícita e auditável via `configs/science/etno_selection.yaml`
  (`min_a_au`, `min_q_au`, validação). Ainda não validado externamente contra
  MPC/JPL/Horizons - blocker `etno_catalog_not_fully_validated` ativo.
- `python main.py report --from-run <run>`: regenera `report.md` incluindo a
  seção "Robustez V2" com os resultados acima, quando existirem.

**Resultado científico honesto já obtido com isso (não é claim novo, é o que
os dados mostraram):** rodando os modelos nulos reais contra o catálogo atual,
nenhum candidato supera consistentemente os três modelos nulos
(`shuffle_varpi`, `randomize_angles`, `no_p9_catalog_baseline`) ao mesmo
tempo. O blocker `null_model_not_exceeded` permanece ativo. Isso não é uma
falha do pipeline - é exatamente o tipo de resultado negativo honesto que
esses testes existem para produzir.

Dois bugs reais foram corrigidos durante a fusão:

- `robustness.py` tinha duas definições da função `null_models` (a segunda
  sobrescrevia a primeira silenciosamente, deixando a primeira como código
  morto nunca executado). A definição morta foi removida.
- `timestamp_id()` havia perdido a precisão de microssegundos mencionada no
  histórico do projeto ("evitando colisão silenciosa de pastas de run"),
  provavelmente durante uma fusão anterior que sobrescreveu `run.py`. Duas
  runs iniciadas no mesmo segundo agora continuam gerando `run_id`s distintos.

Limitações que continuam de pé mesmo com esses comandos implementados:

- Modelo de viés observacional continua ausente (`no_observational_bias_model`).
- Catálogo ainda não validado externamente.
- `write_seed_stability` hoje registra o mesmo rank/delta para todas as seeds
  configuradas em vez de rodar o pipeline completo por seed - é uma medida de
  estabilidade parcial, não uma reamostragem independente de verdade.
  Nenhuma run real do repositório testa estabilidade entre seeds de fato:
  todas usam `seeds: [12345]` (orçamento único), então o resumo sai
  `"enabled": false` (auditoria V3, P1-2). Isso deve permanecer PENDENTE
  explícito no artigo — não elevar "robustez validada" em nenhuma seção.
- O modelo secular/apsidal (`mean_angular_alignment_score`,
  `delta_pomega_stability`) foi pensado para o regime prógrado/moderado
  típico da literatura de Planeta 9 (Batygin & Brown) e **não foi validado
  para `i` próximo de 90° ou retrógrado** (regime Kozai-Lidov). Desde a
  auditoria V3 (P2-4), candidatos com `i_deg >= 80` recebem um blocker
  consultivo (`inclination_out_of_model_regime`, severidade `science_limit`)
  registrado em `audit/blockers.json`, na coluna `blockers` do
  `ranking.csv`/`candidates_status.csv` e no `explain` do candidato — a run
  continua concluindo e o candidato permanece ranqueado, mas o resultado
  nesse regime não pode ser lido como validado. Este é um aviso de regime,
  não uma validação do regime de oscilação Kozai-Lidov.
- Detectabilidade (limites IR/óptico) continua não implementada.

## Fechamento da tarefa 1 (LIMITACOES + artigo) — 2026-08-15

Reconciliação das três localizações da documentação de limitações/artigo
(`docs/LIMITACOES.md`, `docs/Artigo_FEBRACE_revisado.docx` e
`CONSOLIDADO_PLANET9_SCREENING_LAB.md`).

Estado verificado no código e nas runs reais:

- O artigo alega exatamente o que foi executado: as duas runs reais de 1 Myr
  (`angle_robustness`: row6 com ω9 ∈ {0°, 90°, 180°, 200°, 270°};
  `i_boundary_scan`: row4 com i ∈ {31°, 32°, 33°, 34°, 35°}; ambas com
  Ω9=270°, M0=180°). Tabela 2 marca as demais linhas como "Não executado nesta
  versão" e a Seção 9 trata ω9/Ω9/M0 como qualitativos. Consistente.
- `results/hardware_benchmark.json` agora existe com proveniência explícita
  (sandbox), não serve como referência de prazo; ver seção acima.
- Novas ferramentas opcionais, fora do funil: MEGNO experimental (indicador
  auxiliar NÃO calibrado, seed fixa) e Rayleigh/Kuiper (`circular-stats`,
  READ-ONLY). Decisão Categoria B de 2026-08-15: o threshold ad hoc continua
  sendo o default do funil; Rayleigh/Kuiper ficam como diagnóstico.
- Paralelização (Etapa 1) e `exact_finish_time=0` (Etapa 2) concluídas.

Pendências de documentação que permanecem (não apagadas):

- **Funil do artigo (Tabela 5) — RESOLVIDO com artefato real e amostra de
  Estágio 3 reduzida** (execução autorizada em 2026-08-16): o scan real foi
  executado em `runs/montecarlo_20260816T001216569981Z/` gerando
  `results/parameter_space_scan.csv` (20.000 pontos) e
  `results/reduction_funnel_summary.json`. O resultado diverge das estimativas
  ~45%/28%/15%/8%/3-5% que constavam antes: em todos os estágios implementados
  (0-3) 100% dos pontos avaliados foram aprovados. Por isso o artigo foi
  atualizado (Tabela 5 e Seção 7) para reportar o funil real — com nota
  explícita de que o Estágio 3 rodou com apenas 2 ramos (de 60 configurados
  originalmente) por restrição de tempo de execução no sandbox de 2 núcleos
  (~23 min/ramo em 1e8 yr; scan completo ~30 min). Consequência honesta
  registrada no artigo e aqui: **o poder estatístico do funil com essa amostra
  reduzida não foi recalculado** (mesmo princípio aplicado ao Rayleigh/Kuiper);
  os percentuais de "volume restante" (1,0% e 0,01%) refletem o limite de
  capacidade amostral, não eliminação física. Estágios 4/5 continuam
  `not_implemented`. Para elevar o Estágio 3 à amostra completa de 60 ramos é
  necessária nova autorização de execução (escala de horas).

**Atualização 2026-09-03 — scan BB21 (ponto 3 do plano pós-auditoria):**
Um segundo scan foi executado com `configs/montecarlo/parameter_space_bb21.yaml`
(faixa estreita, concentrada no posterior de Brown & Batygin 2021 — ver comentário
no próprio YAML), run `montecarlo_20260903T204715536210Z`. Mesmo resultado
qualitativo do scan BB16: 100% dos pontos avaliados em cada estágio (0-3)
passaram, com o mesmo padrão de `skipped_capacity_limit` explícito (19.800 no
estágio 2, 198 no estágio 3) em vez de truncamento silencioso. **Nota
metodológica sobre comparabilidade:** para tornar este scan comparável ao BB16
de 2026-08-16, `configs/budgets/secular.yaml` foi rebaixado TEMPORARIAMENTE para
1e8 anos durante esta execução e restaurado para 4e9 anos (o alvo definido no
Passo 1 deste lote) logo em seguida — nenhuma run de fato em 4 Gyr foi executada
para o estágio 3 do Monte Carlo em nenhum dos dois scans; ambos permanecem no
horizonte de 1e8 anos, não no horizonte alvo do artigo. Isso deve ser reportado
explicitamente se/quando os scans forem citados no artigo.

**Achado menor (não bloqueia, registrar para correção futura):** o campo
`methodology_note` gravado no JSON de resultado do `montecarlo-scan` cita
literalmente `configs/montecarlo/parameter_space.yaml` como texto fixo no
código, independentemente de qual `--config` foi de fato usado — a run BB21
(`parameter_space_bb21.yaml`) herdou essa string incorreta no `methodology_note`.
Os números/bounds usados na run estão corretos (vêm do YAML real, não do texto);
apenas o rótulo textual está desatualizado. Não usar esse campo do JSON como
fonte ao citar qual config gerou qual run no artigo — usar o nome do arquivo de
config e o run_id, que estão corretos.
- **Proveniência de ω9/Ω9/M0**: os valores 200°/270°/180° são assumidos e
  iguais para as 7 linhas do Quadro 2 (ver `docs/CANDIDATOS_QUADRO2.md`).
  O artigo só os restringe qualitativamente (S9): ω9 ≈ 150°–250° por análises
  de viés, Ω9 no hemisfério sul |b| > 20°, M0 perto do afélio. Variar por linha
  do Quadro 2 é decisão Categoria B, pendente.
