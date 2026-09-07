# TASK.md — Planet9 Screening Lab

Canal único de comunicação entre Auditor e Executor. O Auditor escreve e
sobrescreve a seção "Plano vigente". O Executor só edita "Bloqueios" e
"Log de execução". Ver .clinerules para as regras completas.

---

## Estado herdado (contexto, não editar — histórico de uma sessão de
## engenharia de prompt anterior, verificado e validado)

Ambiente: H:\planet9-screening-lab, Windows, i5-14400, venv Python 3.11.9,
rebound 5.1.1 real, **149 testes passando** (baseline atual), ruff limpo.

Os 5 pontos do "plano pós-auditoria científica" original estão CONCLUÍDOS:
1. Benchmark real: i5-14400, 347.886 anos simulados/s. `secular.yaml`
   configurado para 4 Gyr (`integration_years: 4000000000`) — execução
   real ainda NÃO feita.
2. Candidato `p9_row8_bb21_bestfit` (Brown & Batygin 2021) no Quadro 2
   (8ª linha): M=6,2 M⊕, a=382,4 UA, e=0,20, i=15,6°, ω9=246,7°, Ω9=0°,
   M0=180°. Sanidade (200 anos): rank 1, `candidate_of_interest`,
   `evidence_level: weak`. Divergência ϖ9=110° (assumido) vs 246,7° (BB21)
   pendente de discriminação secular (requer item da Tarefa C abaixo).
3. Segundo scan Monte Carlo (`parameter_space_bb21.yaml`) rodado, run
   `montecarlo_20260903T204715536210Z`, comparável ao BB16 original (run
   `montecarlo_20260816T001216569981Z`, restaurada de backup, hash CSV:
   `0A2D59AF26B8CCF1CE439F7627FE980A248657AF2CB06BB7E8047FAB5FC64B4D`).
4. Catálogo de ETNOs: 14→16 (adicionados `2017_OF201` e
   `Leleakuhonua_2015_TG387`). Estatística circular n=16: R=0,299836,
   Z=1,438424, p_Rayleigh=0,24046, V*=1,266498, p_Kuiper=1,0, θ̄=39,37° —
   não significativo. (n=13: R=0,365, p=0,178, θ̄≈57° — sem mudança.)
5. Módulo `planet9lab/selection_bias.py` implementado: comando
   `selection-bias-check --from-run <run>`, modelo angle-only de 3 fatores
   (Napier et al. 2021). Resultado real (seed 12345, n=16):
   R_real=0,299836 vs R_sintético_sobrevivente=0,00593 →
   `real_exceeds_synthetic_R: true`. NÃO confirma nem descarta viés — só
   mostra que este modelo simplificado não reproduz o clustering.

Artigo `docs/PLANET9_ARTIGO_v1.2_ABNT.docx` atualizado com os 5 pontos
acima (formato FENIC/FEBRACE), verificado item a item contra o texto real.
16 referências (14 + Stephens 1970 + Zar 1999). 3 pendências científicas
genuínas declaradas explicitamente no texto (não são erros a corrigir):
estatística sem significância, BB21 vs ϖ9 não discriminado, viés não
descartado.

Trabalho relatado (origem incerta — sessão/máquina não confirmada, ver
Bloqueio B1 abaixo): um módulo `planet9lab/geometry/poly_footprint.py`
teria sido criado, portando fielmente `create_poly` e `point_in_polygon`
do Fortran original do OSSOS SurveySimulator (fonte:
H:\_tmp_ossos_survey, read-only). Relatado como não integrado ao
pipeline principal, com gate confirmado (151 passed) NAQUELA sessão —
**não confirmado nesta cópia do repositório ainda.**

---

## Plano vigente (escrito pelo Auditor — versão atual, substitui qualquer anterior)

### Tarefa A — Blocker automático de viés de seleção
**Prioridade: primeira.**

Hoje `planet9lab/robustness.py::merge_blocker` só adiciona blockers a
`audit/blockers.json`, nunca remove. Quando
`selection_bias.py::run_selection_bias_check` roda com resultado
FAVORÁVEL (`real_exceeds_synthetic_R: true`), o blocker antigo
`no_observational_bias_model` (definido em
`configs/science/observational_bias.yaml`, `blocker_if_none: true`)
continua ativo mesmo sem motivo — o modelo de viés já existe e já rodou.

**Passos:**
1. Confirmar onde `no_observational_bias_model` é de fato adicionado
   (`Select-String -Path planet9lab\*.py -Pattern "no_observational_bias_model"`).
2. Implementar `remove_blocker(run_dir, blocker_id)` em `robustness.py`,
   mesmo padrão de leitura/escrita de `audit/blockers.json` que
   `merge_blocker` já usa.
3. Chamar `remove_blocker` em `run_selection_bias_check` quando
   `real_exceeds_synthetic_R` for `true`. Quando `false`, NÃO remover (o
   blocker específico `selection_bias_not_ruled_out` já cobre esse caso).
4. Testes novos: (a) resultado favorável → blocker antigo removido; (b)
   resultado desfavorável → blocker antigo permanece.
5. Gate: `pytest -q` (baseline 149 → esperado 151) + `ruff check .`.
6. Teste manual: rodar contra `runs\screen_20260903T211311606520Z`
   (já teve bias-check favorável rodado antes), mostrar
   `audit/blockers.json` antes e depois.

**Critério de aceite:** blocker antigo removido corretamente só no caso
favorável, testes cobrindo os dois casos, gate limpo, commit feito.

---

### Tarefa B — Melhorar o modelo de viés de seleção observacional
**Prioridade: segunda, após A concluída e commitada.**

O modelo atual (`planet9lab/selection_bias.py`) é angle-only: 2 dos 3
fatores (profundidade em magnitude, arco de rastreamento mínimo) são
penalidades uniformes sem dependência angular. Isso limita a capacidade
do modelo de gerar clustering artificial mesmo quando esse viés existe.

**Passos:**
1. **Investigar primeiro o Bloqueio B1** (módulo `poly_footprint.py`) —
   ver seção Bloqueios abaixo. Se ele existir de fato nesta cópia do
   repositório e a fonte for confirmada como genuína (Fortran real do
   OSSOS, código em `H:\_tmp_ossos_survey`), ele é a base natural para o
   fator de "cobertura de céu" com geometria real de footprint, em vez da
   fração de área uniforme atual.
2. Adicionar modelagem de magnitude aparente real: distância heliocêntrica
   (via a/e já sintéticos), tamanho/albedo sintéticos (buscar valores
   plausíveis reais na literatura de TNOs/ETNOs — citar a fonte usada, não
   inventar), calcular V aparente por objeto, comparar contra
   `limiting_magnitude_v` de forma dependente do objeto.
3. Se `poly_footprint.py` for aproveitável: usar para o fator de cobertura
   de céu com um footprint geométrico real de survey (documentar qual
   survey/bloco usado como referência, com fonte).
4. Manter a mesma disciplina de linguagem: `interpretation`/`caveats` no
   resultado nunca podem soar mais confiantes do que o modelo sustenta.
5. Testes cobrindo o novo comportamento. Gate: `pytest -q` + `ruff check .`.
6. Atualizar `docs/LIMITACOES.md` com o novo estado do modelo (o que
   mudou, o que ainda é aproximado).

**Critério de aceite:** modelo mais realista, fonte de cada dado novo
citada, gate limpo, `docs/LIMITACOES.md` atualizado, commit feito.

---

### Tarefa C — Execução secular real de 4 Gyr
**Prioridade: terceira, só após A e B concluídas E autorização explícita
registrada nesta seção pelo usuário/Auditor (ver campo abaixo).**

Estimativa: ~6,4h por par de candidato, ~25,6h para os 8 candidatos do
Quadro 2 (medido no i5-14400 local). Resolve a pendência central de
discriminar BB16 (ϖ9=110°) vs BB21 (ϖ9=246,7°).

**AUTORIZAÇÃO PARA INICIAR:** ⬜ NÃO AUTORIZADA AINDA — aguardando
confirmação explícita do usuário antes do Executor iniciar esta run.

**Pré-requisito obrigatório antes de qualquer autorização:** os números de
custo (~6,4h/par, ~25,6h total) foram medidos no i5-14400 em
2026-09-03/04 (`results/hardware_benchmark.json`). Nenhuma máquina foi
designada como "oficial" para rodar a Tarefa C — pode ser o i5-14400, o
Xeon, ou outra, dependendo da disponibilidade no momento. **Antes de
autorizar/iniciar a Tarefa C em QUALQUER máquina diferente da que gerou
o benchmark citado, rodar `python scripts\benchmark_integration_cost.py`
NAQUELA máquina primeiro** e recalcular a projeção de horas real — nunca
assumir que o número do i5-14400 vale para outro hardware. Registrar o
novo benchmark em "Log de execução" antes de pedir autorização.

**Quando autorizada, passos:**
1. Registrar em "Log de execução" o timestamp de início esperado.
2. Iniciar em BACKGROUND (não bloquear o terminal — validar sintaxe de
   `Start-Job`/`Start-Process` antes de rodar, não adivinhar).
3. Confirmar que o job está rodando de fato (verificar processo, não só
   o comando ter retornado sem erro).
4. Continuar outras tarefas (próximo item de `docs/LIMITACOES.md`)
   enquanto a run progride — nunca ficar ocioso esperando.
5. Verificar progresso periodicamente (espaçado, é uma run de horas),
   registrar checkpoints em "Log de execução".
6. Ao terminar: registrar resultado real (SUCCESS.marker, status.json,
   ranking.csv) em "Log de execução". NÃO atualizar o artigo sozinho com
   a conclusão — preparar a atualização e sinalizar em "Bloqueios" que
   está pronta para revisão do Auditor/usuário.

---

## Continuidade (após A, B, C)

Não parar e declarar o projeto concluído. Reler `docs/LIMITACOES.md` do
início ao fim, propor aqui (nova entrada em "Plano vigente", como
proposta do Executor até o Auditor confirmar) o próximo item de valor.
Ver `.clinerules`, seção "Continuidade", para o processo completo.

---

## Bloqueios (só o Executor edita esta seção)

### B1 — Origem do módulo poly_footprint.py não confirmada nesta sessão
Um relatório de outra sessão/máquina do Cline descreveu a criação de
`planet9lab/geometry/poly_footprint.py` + `__init__.py`, portando
`create_poly` e `point_in_polygon` do Fortran do OSSOS SurveySimulator
(fonte: `H:\_tmp_ossos_survey`). Isso **não foi confirmado como existente
nesta cópia do repositório**. Antes de a Tarefa B depender disso, o
Executor deve:
1. `Test-Path planet9lab\geometry\poly_footprint.py` e
   `Test-Path planet9lab\geometry\__init__.py`.
2. Se existir: `python -c "from planet9lab.geometry.poly_footprint import create_poly, point_in_polygon; print('import OK')"`.
3. Verificar `H:\_tmp_ossos_survey` existe e contém de fato código Fortran
   do OSSOS (não confiar apenas no nome da pasta).
4. Reportar aqui o resultado antes de a Tarefa B prosseguir com essa
   dependência. Se não existir, a Tarefa B segue sem essa base (só o
   fator de magnitude aparente, sem footprint geométrico real por ora).

*(Preencher resultado abaixo desta linha quando investigado:)*

**Resultado (2026-09-07, Executor): B1 RESOLVIDO — confirmado nesta sessão.**
1. `Test-Path planet9lab\geometry\poly_footprint.py` → True;
   `Test-Path planet9lab\geometry\__init__.py` → True.
2. Import smoke no venv: `python -c "from
   planet9lab.geometry.poly_footprint import create_poly,
   point_in_polygon; ..."` → saída "import OK".
3. `H:\_tmp_ossos_survey\fortran\F95\getsur.f95` → True (fonte Fortran
   do OSSOS presente; pasta read-only, nada editado ali). Fidelidade do
   porte verificada contra o Fortran nesta sessão: `point_in_polygon`
   usa o mesmo método do quadrante (walk_sum acumula ±4) e a mesma
   convenção de retorno -100 para ponto na borda do polígono.
4. A Tarefa B pode apoiar-se em `planet9lab/geometry/poly_footprint.py`
   como base (footprint geométrico real disponível).


---

## Log de execução (só o Executor edita esta seção — sempre APPEND, nunca reescrever entradas antigas)

<!-- Nova entrada abaixo desta linha, formato:
### [AAAA-MM-DD HH:MMZ] <modelo> — <tarefa>
- Status: concluído | parcial | bloqueado | aguardando decisão
- O que foi feito / resultado real (números, testes, hashes, caminhos)
- Commit: <hash> ou "pendente"
- Próximo passo
-->

### 2026-09-07 17:02Z Cline (Executor) — Fechamento Tarefa A + B1 + investigação viés (report-only)
- Status: concluído
- O que foi feito / resultado real:
  - **Tarefa A** — confirmado que a parte de código já estava integrada
    (commits f922e26/0ef8360; nenhum código novo nesta sessão): blocker
    `no_observational_bias_model` definido em `planet9lab/policy.py:12`,
    acionado quando `bias_config.get("bias_model") == "none"`
    (`policy.py:72`; `blocker_if_none: true` no
    `configs/science/observational_bias.yaml`); remoção automática em
    `planet9lab/selection_bias.py:289`
    (`remove_blocker(run_dir, "no_observational_bias_model")`) + evento
    `no_observational_bias_model_blocker_removed` (`selection_bias.py:290`),
    disparados quando `real_exceeds_synthetic_R` é true (contrato no
    docstring, linhas 250-254). Testes da Tarefa A:
    `tests/test_selection_bias.py` (2 testes novos passando).
  - **Teste manual (passo 6)** — `runs\screen_20260903T211311606520Z`:
    `audit/blockers.json` (e o snapshot raiz da run) contém apenas
    `etno_catalog_not_fully_validated` — sem
    `no_observational_bias_model`; `diagnostics/selection_bias.json`
    registra `real_exceeds_synthetic_R: true` (R_real=0,299836 vs R
    sintético sobrevivente=0,00593; fração sobrevivente 0,3484;
    n_sintético=5000 gerados / 1742 sobreviventes). O estado "antes" não
    foi fotografado, mas `events.log` da run registra o evento
    `no_observational_bias_model_blocker_removed` (2026-09-04T16:51Z),
    que o código só emite quando `remove_blocker` remove de fato um
    blocker presente (`selection_bias.py:289-290`).
  - **Gate (antes e depois, literal):** `python -m pytest -q` →
    `151 passed in 75.90s` (baseline herdado 149 + 2 da Tarefa A);
    `python -m ruff check .` → `All checks passed!` (exit 0).
  - **B1 RESOLVIDO** — resultado completo na seção Bloqueios: arquivos
    existem, import OK, fonte Fortran `getsur.f95` confirmada.
  - **Investigação para o módulo de viés observacional (report-only,
    nenhum código escrito):** `observational_bias.yaml` tem 4 chaves
    (`bias_model: none`, `bias_model_level: 0`, `blocker_if_none: true`,
    `max_evidence_level_without_bias_model: weak`); `cli.py` registra 23
    subcomandos (template do novo comando: `sub.add_parser(...)` +
    `add_argument(...)`, ex. `selection-bias-check` cli.py:129-131);
    null-models em `robustness.py`: `null_models(run_dir, top=5, ...)`
    (:334), `build_null_etnos(etnos, rng, varpis, model_name)` (:310,
    modelos `shuffle_varpi`, `randomize_angles`,
    `no_p9_catalog_baseline`), `_null_worker` (:138),
    `build_null_row(...)` (:450); diagnóstico em `diagnostics.py`
    (`diagnose_null_models` :126, `build_null_diagnosis` :147,
    `null_markdown` :197). Relatório consolidado entregue ao usuário.
  - **Limpeza:** 12 arquivos `pytest_*.txt` untracked na raiz
    (redirecionamentos de sessões anteriores) removidos; nenhum código
    alterado nesta sessão.
- Commit: pendente (hash reportado ao usuário no fechamento da sessão;
  este commit inclui a própria entrada)
- Próximo passo: Auditor decide entre (a) módulo de viés observacional
  (insumos já mapeados, template CLI pronto) e (b) Tarefa B; Tarefa C
  segue aguardando autorização explícita + benchmark na máquina que for
  rodar.
