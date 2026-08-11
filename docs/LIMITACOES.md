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
  existe para medir isso (tempo de parede real por candidato), mas só pode ser
  executado numa máquina com REBOUND instalado e tempo disponível - não
  neste ambiente de desenvolvimento (sem rede, sem REBOUND). Enquanto
  `results/hardware_benchmark.json` não existir, `integration_years` é uma
  escolha conservadora de ponto de partida, não um valor testado. Se ao rodar
  o benchmark 4e9 anos (ou mesmo 1e9) não couber no orçamento de tempo
  disponível, o artigo deve reportar o maior valor efetivamente executado, não
  o valor originalmente pedido.
- Catálogo canônico ainda usa fixtures parciais.
- Não há modelo completo de viés observacional.
- Leave-one-out não é executado.
- Propagação de incerteza não é executada.
- Modelos nulos extras (além do controle com/sem P9) não são executados.
- Detectabilidade (limites IR/óptico) não é executada.
- MCMC/Monte Carlo real sobre `[M9, a9, e9, i9]` ainda não existe (item 2 do
  plano V1->V2 - próximo bloco a implementar).
- Candidatos de exemplo ainda não foram substituídos pelos do Quadro 2 do
  artigo (item 3).
- Rastreabilidade artigo<->run (`article_section_ref`, `export_to_article.py`)
  ainda não existe (item 4).

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
- Detectabilidade (limites IR/óptico) continua não implementada.
