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

### Tarefa D — Dashboard de controle e visualização de runs
**Prioridade: paralela — não bloqueia nem é bloqueada pelo Item 1
(verificação do impacto do bugfix de cabeamento) nem pela Tarefa C.
Modo de execução: AUTÔNOMO (não aguardar confirmação a cada passo;
seguir até o critério de aceite ou até um dos dois bloqueios reais
definidos abaixo).**

Decisão de arquitetura (Auditor, já resolvida — não reabrir): **NiceGUI**.
Motivo: projeto 100% Python, precisa disparar processos longos (a Tarefa C
pode levar ~25h) sem travar a UI, e reaproveita funções/comandos do
`cli.py` diretamente sem duplicar lógica em outra linguagem.

**Escopo (4 funcionalidades):**
1. Disparo de comandos do `cli.py` via formulário na UI, sem digitar no
   terminal.
2. Acompanhamento de progresso de runs em andamento (barra de progresso
   ligada aos checkpoints que o pipeline já grava).
3. Listagem de runs passadas: run_id, started_at/ended_at, status,
   global_result_status como badge, blockers ativos como alerta visual.
4. Relatório legível por run, lendo das pastas canônicas (evitar os
   arquivos duplicados na raiz da run): `results/` (ranking, métricas,
   candidatos), `audit/` (blockers, manifest), `diagnostics/`
   (diagnósticos de viés e afins), `status.json` (raiz da run, não
   duplicado).

**Restrições de escopo (não negociável):**
- Não alterar `cli.py` nem qualquer módulo de `planet9lab/` existente —
  o dashboard só CHAMA os comandos já existentes (via subprocess ou
  invocação de função), nunca refatora ou modifica o que já está testado.
- Servidor NiceGUI deve bindar apenas em localhost/127.0.0.1 — nunca
  0.0.0.0 nem exposto na rede.
- Qualquer arquivo novo de estado/log/cache que o dashboard gerar (ex:
  PID files, temp de sessão) deve ser adicionado ao `.gitignore` no
  mesmo commit — não deixar arquivos soltos não-rastreados na raiz
  (mesmo problema já visto e limpo antes com os `pytest_*.txt`).

**Requisito não negociável (disciplina científica):** qualquer campo
`caveats`/`interpretation` presente nos JSONs de diagnóstico deve aparecer
no relatório da run NA ÍNTEGRA — sem paráfrase, resumo ou corte. Números
(R, p-valor, scores) vêm direto dos arquivos, nunca recalculados ou
aproximados na camada de UI. Escrever um teste automatizado que verifica
programaticamente que todo texto de caveats/interpretation do JSON de
origem aparece literalmente (substring exata) na saída/HTML do relatório
gerado — este teste faz parte do gate, não é opcional.

**Requisito de runs longas:** disparar via subprocess/processo
independente da sessão da UI — uma run não pode depender de manter a
aba/navegador aberta para sobreviver (crítico para a futura Tarefa C).
Antes de declarar esse requisito bloqueado/incompatível, tentar pelo
menos duas abordagens padrão (ex: `subprocess.Popen` desacoplado do
processo pai + arquivo de status; ou `Start-Job`/processo de SO
independente) e documentar o resultado de cada tentativa no Log — só
reportar bloqueio real se ambas falharem, com evidência do que foi
tentado.

**Ordem recomendada:** adicionar a dependência (nicegui) e rodar o gate
imediatamente (`pytest -q` + `ruff check .`) antes de escrever qualquer
código novo — isolar cedo qualquer conflito de dependência do resto do
trabalho.

**Bloqueios que interrompem o modo autônomo (só estes dois):**
(a) uma decisão exigir um dado/número que não existe no repositório nem
em fonte confiável (mesma regra de nunca deduzir valores); ou (b) o
requisito de runs sobreviverem ao fechamento da UI se mostrar
incompatível após as duas tentativas documentadas. Em ambos os casos:
documentar o bloqueio específico em "Bloqueios" e continuar o restante
do escopo que não depende dele — não parar o trabalho todo.

**Critério de aceite:** as 4 funcionalidades do escopo funcionando,
teste de integridade de caveats/interpretation passando, runs longas
sobrevivem ao fechamento da UI (com evidência da tentativa), restrições
de escopo respeitadas (`cli.py` intocado, bind local apenas,
`.gitignore` atualizado), gate limpo (`pytest -q` + `ruff check .`),
commit feito, decisões de arquitetura documentadas no Log.

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

### B2 — Atualização do artigo: informação pronta, aguardando decisão do Auditor (informativo, não bloqueia execução)
A run `screen_20260903T211311606520Z` passou por execução OFICIAL do
`selection-bias-check` com a config canônica corrigida (filling factor
0,9067 — ver Log 2026-09-09), que substitui o artefato antigo (fallback
≈0,485) como referência válida do projeto. A conclusão
(`real_exceeds_synthetic_R: true`) se mantém — nenhum texto científico
existente fica invalidado. SE o Auditor julgar necessário citar no artigo
os números novos (R sintético 0,032567 vs 0,00593 do artefato antigo,
sobrevivência 0,1918 vs 0,3484), a atualização do
`docs/PLANET9_ARTIGO_v1.2_ABNT.docx` está PRONTA para preparação, mas
EXIGE autorização explícita e separada (nenhum .docx foi tocado).
Backup do artefato antigo: `%TEMP%\p9_bias_recheck\selection_bias_OFFICIAL_PRE_20260909.json`.


---

## Log de execução (só o Executor edita esta seção — sempre APPEND, nunca reescrever entradas antigas)

<!-- Nova entrada abaixo desta linha, formato:
### [AAAA-MM-DD HH:MMZ] <modelo> — <PC: hostname ou identificador> — <tarefa>
- Status: concluído | parcial | bloqueado | aguardando decisão
- O que foi feito / resultado real (números, testes, hashes, caminhos)
- Commit: <hash> ou "pendente"
- Próximo passo
- PC: <hostname ou identificador> — $env:COMPUTERNAME do Windows (ex.: ALUNOSENAI). OBRIGATÓRIO em toda entrada.
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

### 2026-09-07 20:30Z Cline (Executor) — Módulo de viés observacional: H-prior do SBDB
- Status: concluído
- O que foi feito / resultado real:
  - **Dados H do JPL SBDB** — `data/etnos/h_values.csv` criado com 16 valores
    de magnitude absoluta H (um por ETNO do `catalog_validated.csv`),
    consultados via `sbdb.api?sstr=<des>&phys-par=1` em 2026-09-07. Cada
    linha tem `object`, `h`, `ref` (solution identifier do SBDB),
    `sigma` (quando disponível), `notes`. Attribution doc em
    `data/etnos/h_values_attribution.md` com URL, query pattern, e
    albedo (0,10 Sheppard & Trujillo 2016 AJ 152:221).
  - **Código `planet9lab/selection_bias.py`**:
    - `load_h_catalog(path)` lê CSV (pula linhas `#`), valida colunas
      `object`/`h`, retorna lista de `(fullname, h_value)`.
    - `_depth_prob_from_h(h, V_lim)` = stand-in linear: base da profundidade
      (1 − 0.15·(24.5−V_lim)) menos penalidade 0.12 por magnitude acima da
      mediana (6.5); objetos mais brilhantes NÃO são boostados
      (conservativo). TODO documentado: substituir por V = H + 5 log10(r·Delta)
      quando a população sintética carregar distância heliocêntrica.
    - `ObservationalBiasConfig` ganha `h_catalog_path` (default
      `data/etnos/h_values.csv`) e `albedo_default` (0,10, validador
      [0.01, 0.60]). Novo `bias_model: h_prior_from_catalog`.
    - `generate_synthetic_population()` agora aceita `h_catalog` (lista de
      H) e sorteia um H por objeto (com reposição) — população sintética
      replica o brilho da amostra real, ângulos continuam uniformes.
    - `apply_selection_function()` usa `_depth_prob_from_h()` por objeto
      quando `h_catalog` fornecido (em vez de probabilidade fixa).
    - `selection_bias_check()` retorna `h_prior_source`, `n_h_values`,
      `h_min/h_max/h_median` no resultado; `synthetic_R` continua reportado.
  - **Testes** — `tests/test_selection_bias.py` ganha 11 novos testes
    (total 162): h_prior sob `h_prior_from_catalog`, guardas anti-vacuo,
    validação de albedo fora do range, reprodutibilidade real vs sintético,
    deterministicidade, e shape do resultado.
  - **`configs/science/observational_bias.yaml`** — alterado
    `bias_model: none` → `bias_model: h_prior_from_catalog`.
  - **`docs/LIMITACOES.md`** — seção do modelo de viés atualizada com a
    nova versão H-prior, limitações documentadas (angle-only, stand-in
    linear não calibrado, TODO de magnitude aparente real), e
    atribuição SBDB.
  - Nenhum teste existente quebrado (baseline 151 → 162); ruff limpo.
- Commit: `4adec0f` (6 files changed, 399 insertions, 59 deletions)
- Próximo passo: Auditor decide — (a) refinar o modelo de viés com
  magnitude aparente real (requer distância/tamanho/albedo sintéticos,
  footprint de survey), (b) executar `selection-bias-check` em runs reais
  com a nova config, ou (c) avançar para Tarefa B.

### 2026-09-07 22:00Z Cline (Executor) — Modelo de eficiência de detecção OSSOS (Bannister+ 2018)
- Status: concluído
- O que foi feito / resultado real:
  - **Curva logística-quadrática de eficiência** — Implementada
    `_efficiency_square(m, eff_max, c, m0, sig)` com forma funcional
    `η(m) = (eff_max − c·(m−21)²) / (1 + exp((m−m0)/σ))` de Bannister et al.
    2018, ApJS 236:18 (arXiv:1805.11740), §5.2, Tabela 2 (survey "2013 AE"):
    `eff_max=0.86`, `c=0.013`, `m0=24.0` (mag limite 50% eficiência),
    `σ=0.35` (largura da queda).
  - **Magnitude aparente real por objeto** — `_apparent_magnitude(H, r, Δ)`
    calcula `V = H + 5·log10(r·Δ)` (definição padrão).
  - **r/Δ sintéticos na população** — `generate_synthetic_population()` agora
    aceita `q_catalog` (lista de q do catálogo) e gera:
    - `q_au`: sorteado do catálogo com reposição (q-prior);
    - `r_au`: aproximação do afélio `a·(1+e)`;
    - `delta_au`: `r_au − 1.0` (geocêntrica simplificada).
    TODO documentado: r/Δ são aproximações conservadoras, não integração
    orbital completa.
  - **Pipeline de seleção integrado** — `apply_selection_function()` agora
    ramifica: (a) se r/Δ e `ossos_efficiency_params` disponíveis →
    eficiência OSSOS; (b) senão se `h_value` disponível → stand-in linear
    `_depth_prob_from_h()`; (c) senão → probabilidade fixa original.
    Backward-compatível: populações sem distância/H continuam funcionando.
  - **Config `observational_bias.yaml`** — nova seção `ossos_efficiency`
    com os 4 parâmetros publicados; `bias_model` permanece
    `h_prior_from_catalog` (o OSSOS é um filtro adicional, não substituto).
  - **Atribuição** — `data/etnos/ossos_efficiency_attribution.md` criado
    citando Bannister+ 2018 (ApJS 236:18, arXiv:1805.11740) e Bannister+
    2016a (OSSOS survey simulator) com valores exatos da Tabela 2.
  - **Testes** — `tests/test_selection_bias.py` ganha 5 novos testes
    (total 167): eficiência OSSOS (objeto brilhante sobrevive, objeto
    fraco não), `_apparent_magnitude` (Sanity check), geração de r/Δ
    (shape e coerência com q), determinismo, e integração com q-prior.
  - **LIMITACOES.md** — seção expandida: modelo completo documentado,
    simplificações sinalizadas (OSSOS footprint real ainda não filtra
    por posição angular, r/Δ via cinemática 2D), TODO de footprint real.
  - Gate: **167 passed in 89.83s**, ruff limpo. Árvore limpa.
- Commit: `7d5afb2` (push para origin/main)
- Próximo passo: Auditor decide — (a) integrar footprint real do OSSOS
  (blocos em `data/ossos_2013a_blocks.py`) como filtro posicional,
  (b) executar `selection-bias-check` em runs reais com a nova config, ou
  (c) avançar para Tarefa B.


### 2026-09-07 22:45Z Cline (Executor) — Filling factor OSSOS como substituto de sky_coverage
- Status: concluído (bugfix sobre a implementação do commit 7d5afb2)
- O que foi feito / resultado real:
  - **`planet9lab/selection_bias.py:368-369`**: corrigido `NameError` — a variável `sky_survival_prob` (definida na linha 349-351 com `ossos_filling_factor` ou fallback `sky_coverage_deg2/41253.0`) não estava sendo usada no teste Bernoulli; o código referenciava `sky_fraction` (nome inexistente). Substituído por `sky_survival_prob`.
  - **`caveats` expandido de 3 para 4**: adicionada entrada documentando o filling factor OSSOS (0,9067) como aproximação uniforme (angle-only, sem POS real para teste point-in-polygon).
  - **`docs/LIMITACOES.md`**: atualizada para refletir que a cobertura de céu agora usa o filling factor médio publicado do OSSOS (0,9067) em vez da aproximação `sky_coverage_deg2/41253`, mantendo documentada a limitação de não ter filtragem posicional real por bloco.
  - **`data/etnos/ossos_efficiency_attribution.md`**: seção "OSSOS filling factor" adicionada com valores (0,9079 [2013A-E], 0,9055 [2013A-O], média 0,9067) e atribuição a Bannister et al. 2016a / OSSOS SurveySimulator.
  - **`tests/test_selection_bias.py:219`**: ajustada asserção `len(result["caveats"]) == 3` → `>= 4` (o teste valida que os 4 caveats existem; futuros caveats não quebram o contrato).
- Commit: `9956415` (4 files changed, 67 insertions, 12 deletions; push para origin/main).
- Próximo passo: Auditor decide — (a) integrar footprint real dos blocos OSSOS como filtro posicional (requer projeção orbital → posição angular no céu), (b) executar `selection-bias-check` em runs reais com a nova config, ou (c) avançar para Tarefa B.

### 2026-09-09 01:01Z Cline (Executor) — Tarefa B passo 3: footprint geométrico real OSSOS (opt-in) + correção de cabeamento do filling factor
- Status: concluído. Gate final ANTES do commit: `python -m pytest -q` → **173 passed in 76.78s** (baseline 167 do commit 9956415 + 6 testes novos); `python -m ruff check .` → **All checks passed!**.
- O que foi feito / resultado real:
  - **Filtro posicional real (opt-in)** — `apply_selection_function()` ganhou `ossos_footprint_blocks: list[dict] | None`. Quando fornecido e a população carrega `ra_deg`/`dec_deg`, objetos fora de todos os polígonos dos blocos OSSOS 2013A são rejeitados pela nova `_sky_position_in_footprint()` (usa `create_poly`/`point_in_polygon` do porte fiel `planet9lab/geometry/poly_footprint.py`, do Fortran `poly_lib.f95`; convenção idêntica ao SurveySimulator: retorno `!= 0` = dentro ou na borda, mesma lógica `in_poly > 0`). Sobreviventes ainda passam pelo acceptance de Monte Carlo `ossos_filling_factor` (0,9067) — sequência de fatores do simulador original preservada.
  - **`generate_synthetic_population(generate_sky_position: bool = False)`** — gera `ra_deg` (uniforme 0–360°) e `dec_deg` (uniforme −90–90°) somente quando solicitado, preservando o fluxo RNG (e as expectativas semeadas) dos chamadores sem footprint. Proxy declarado em docstring/caveat: NÃO é projeção orbital→céu; uniforme em dec, não isotrópico em área.
  - **`selection_bias_check()`** — com `use_ossos_footprint: true`, carrega `OSSOS_2013A_BLOCKS` (`planet9lab/data/ossos_2013a_blocks.py`) dinamicamente e repassa os blocos ao filtro; resultado ganha `ossos_footprint_mode` (`real_footprint_polygons` | `uniform_filling_factor`) e os caveats ramificam por modo.
  - **CORREÇÃO DE CABEAMENTO — muda comportamento de runs reais (declarado)** — `selection_bias_check()` agora passa `ossos_filling_factor=config.ossos_filling_factor` a `apply_selection_function()`. Até o commit 9956415 esse parâmetro NÃO era passado no ponto de entrada: execuções reais de `selection-bias-check` usavam na prática o fallback `sky_coverage_deg2/41253` (≈0,485 com sky_coverage_deg2=20000), e não o 0,9067 documentado em LIMITACOES.md/caveats. Runs futuros usam 0,9067 → a amostra sintética sobrevivente muda → resultados de `selection-bias-check` anteriores e posteriores a esta correção NÃO são diretamente comparáveis. Testes semeados existentes continuam passando (asserções direcionais, não de valor exato de R).
  - **Config `observational_bias.yaml`** — `use_ossos_footprint: false` (padrão DESLIGADO de propósito: footprint 2013A cobre ~0,07% da esfera celeste e as posições sintéticas são proxies uniformes → ativar por padrão colapsaria a amostra e mudaria a interpretação de todo run padrão sem declaração) e `ossos_footprint_blocks: null` (override manual).
  - **Atribuição** — `data/etnos/ossos_efficiency_attribution.md`: nova seção "OSSOS 2013A footprint block geometry (point-in-polygon positional filter)" — geometria de `planet9lab/data/ossos_2013a_blocks.py` (extraída do OSSOS SurveySimulator, commit a1fcf1bfc146b7b72654d65d6789c59790e3cbb4, clone read-only `H:\_tmp_ossos_survey`), fonte Bannister et al. 2018, ApJS 236:18, Fig. 1; ativação e comportamento documentados.
  - **Testes (6 novos, 167 → 173)** — `test_sky_position_in_footprint_true_for_block_center`, `test_sky_position_in_footprint_false_for_far_position`, `test_apply_selection_function_footprint_rejects_outside_objects` (filling factor 1.0 isola a geometria), `test_apply_selection_function_without_footprint_keeps_uniform_behavior` (backward-compat), `test_selection_bias_check_default_reports_uniform_filling_mode` (seed 12345), `test_selection_bias_check_with_footprint_enabled_reports_real_mode` (+ caveat menciona point-in-polygon).
  - **`docs/LIMITACOES.md`** — nova "Atualização 2026-09-08 — footprint geométrico real do OSSOS como filtro posicional (opt-in)"; bullet de cobertura de céu reescrito (inclui a correção de cabeamento e a não-comparabilidade de runs); novo bullet do proxy RA/Dec (uniforme em dec, não isotrópico; footprint geometricamente real mas astrofisicamente não informativo enquanto proxy); "Próximos passos" atualizados para projeção orbital→céu verdadeira.
- Arquivos alterados: `planet9lab/selection_bias.py`, `configs/science/observational_bias.yaml`, `tests/test_selection_bias.py`, `data/etnos/ossos_efficiency_attribution.md`, `docs/LIMITACOES.md` (commit de código), + `TASK.md` (esta entrada, commit de docs).
- Vocabulário: nada aqui confirma nem descarta viés de seleção; o modo footprint é exercício geométrico do porte fiel, não evidência de clustering induzido por seleção.
- Commit: `f67a155` (5 files changed, 322 insertions, 11 deletions; entrada registrada em commit docs em seguida, push para origin/main).
- Próximo passo: Auditor decide — (a) projeção orbital→céu verdadeira para tornar o filtro de footprint astrofisicamente informativo, (b) executar `selection-bias-check` em runs reais com a nova config, ou (c) avançar para Tarefa C (requer autorização explícita já prevista no plano).

### 2026-09-09 01:32Z Cline (Executor) — Item 1 (prioridade imediata do Auditor): verificação do impacto do bugfix de cabeamento `f67a155`
- Status: concluído (verificação pura — nenhuma linha de código alterada, comando existente rodado duas vezes).
- Procedimento e decisões declaradas:
  - A run de referência `screen_20260903T211311606520Z` NÃO foi mutada: `runs/` é gitignored (`.gitignore:37 runs/*/`), então sobrescrever `diagnostics/selection_bias.json` dela seria irrecuperável. As duas execuções rodaram contra uma CÓPIA verbatim do esqueleto da run (`audit/run_manifest.json` com `seed: 12345`, `audit/blockers.json`, `data_manifest.json`) em `%TEMP%\p9_bias_recheck\`. Os guardas do próprio comando garantem mesma amostra: `_resolve_run_etno_catalog` resolve `data\etnos\catalog_validated.csv` e recusa rodar se os ETNOs selecionados não reproduzirem `included_etnos` do data_manifest (16/16 ✓); `read_manifest` fornece o seed 12345 ✓.
  - Isolamento do efeito do cabeamento: `ObservationalBiasConfig.ossos_filling_factor` é `float` (não aceita `null` via YAML) e o fallback `sky_coverage_deg2/41253` só dispara quando `None` — via CLI o fallback ficou inalcançável após `f67a155`. O CONTROLE usa `ossos_filling_factor: 0.48481322570479723` (= `repr(20000.0/41253.0)`, a probabilidade de sobrevivência de céu EFETIVA pré-`f67a155`) com todo o resto idêntico à config canônica — matematicamente equivalente ao comportamento antigo dentro do modelo atual.
  - Contexto honesto: a run de referência (2026-09-03) PRECEDE o próprio repositório git (commit inicial `f922e26` é de 2026-09-07). Entre o artefato antigo e a config atual o modelo evoluiu (`4adec0f` H-prior SBDB; `7d5afb2` curva de eficiência OSSOS + distância/q-prior; `9956415` filling factor; `f67a155` cabeamento). Logo, antigo-vs-novo NÃO isola só o cabeamento — quem isola é o CONTROLE (modelo atual + fallback).
- Números lado a lado (seed 12345, n=16, `catalog_validated.csv`; `R_real = 0,299836` em todos):
  - ANTIGO (artefato `diagnostics/selection_bias.json` de 2026-09-03, modelo angle-only pré-repo, fallback ≈0,485): R_sintético = **0,00593**; sobreviventes = **1742/5000**; surviving_fraction = **0,3484**; `real_exceeds_synthetic_R` = **true**. (Backup do artefato em `%TEMP%\p9_bias_recheck\selection_bias_OLD_20260903.json`; valores já registrados verbatim em "Estado herdado".)
  - CONTROLE (modelo atual pós-`f67a155` + `ossos_filling_factor: 0.48481322570479723`): R_sintético = **0,01455**; sobreviventes = **489/5000**; surviving_fraction = **0,0978**; `real_exceeds_synthetic_R` = **true**; `bias_model = h_prior_from_catalog`; `ossos_footprint_mode = uniform_filling_factor`.
  - NOVO (modelo atual + `ossos_filling_factor: 0.9067` cabeado — config canônica): R_sintético = **0,032567**; sobreviventes = **959/5000**; surviving_fraction = **0,1918**; `real_exceeds_synthetic_R` = **true**; `bias_model = h_prior_from_catalog`; `ossos_footprint_mode = uniform_filling_factor`.
- Veredito (passo 3 do Auditor): **a conclusão central se MANTÉM** — `real_exceeds_synthetic_R: true` nos três cenários. O efeito do cabeamento foi na direção esperada e declarada no Log `f67a155`: fator de céu menos restritivo (0,485 → 0,9067) → mais sobreviventes (489 → 959) → R sintético SOBE (0,01455 → 0,032567 no modelo atual), i.e., o modelo de viés corrigido fica MAIS capaz de gerar clustering — mas ainda ~9,2× abaixo de R_real (0,299836/0,032567 ≈ 9,2; no artefato antigo a razão era ~50×, inflada pelo modelo angle-only mais restritivo). O clustering real continua não sendo trivialmente explicado por este modelo de viés simplificado.
- Consequência (passo 4): resultado mantém a conclusão → **nada registrado em "Bloqueios"**; nenhuma atualização de artigo/conclusões dependentes é necessária por este item.
- Observações registradas (sem mudança de código neste item):
  - O caveat de sky coverage é texto estático e cita "mean 0.9067" mesmo quando a config usa outro valor (visível no run de controle com 0.4848) — imprecisão cosmética de documento; tratar em tarefa própria se o Auditor julgar relevante.
  - O reconciliation de blockers do caminho favorável (`remove_blocker`) rodou apenas na cópia Temp; o estado de auditoria da run de referência permanece intocado (o `blockers.json` dela já contém só `etno_catalog_not_fully_validated`, então o evento favorável seria no-op lá também).
- Commit: docs (esta entrada + Tarefa D adicionada ao "Plano vigente" por instrução explícita do Auditor).
- Próximo passo: Item 2 — Tarefa D (dashboard NiceGUI) em modo autônomo, começando pela adição da dependência `nicegui` + gate imediato (`pytest -q` + `ruff check .`) antes de qualquer código novo.

### 2026-09-09 03:45Z Cline (Executor) — Item 2 / Tarefa D: dashboard de controle e visualização de runs (NiceGUI, modo autônomo)
- Status: concluído (critério de aceite atendido; nenhuma das duas condições de interrupção do modo autônomo ocorreu).
- Sequência seguida (conforme ordem recomendada do plano): dependência `nicegui` adicionada ao `pyproject.toml` e gate rodado IMEDIATAMENTE antes de qualquer código novo — sem conflito de dependência (instalação limpa no venv; baseline 173 passed mantido).
- Decisões de arquitetura do Executor (documentadas conforme exigido):
  - **Estrutura:** pacote novo `dashboard/` (8 módulos): `config.py` (raízes de paths; porta 8765), `commands.py` (schema curado dos subcomandos do `cli.py` + `validate()` + `build_argv()`), `runner.py` (lançador desacoplado + registro de jobs), `runstore.py` (leitura read-only das pastas canônicas), `report.py` (HTML por run), `app.py` (UI NiceGUI), `__main__.py` (`python -m dashboard`), `__init__.py`. Estado do dashboard em `.dashboard/` (jobs + logs de lançamento) — adicionado ao `.gitignore` NO MESMO COMMIT do código (regra do plano; nada solto não-rastreado).
  - **Mapeamento formulário → cli.py:** schema `COMMANDS` em `commands.py` declara grupo, `long_running`, descrição e args (kind `str|int|float|path|path_run|flag`) de cada subcomando; o formulário gera inputs por arg e `launch()` monta `argv` na ordem do schema e spawna `python -m planet9lab.cli <cmd> <argv>`. A fidelidade do schema é garantida por TESTE que introspeciona o `ArgumentParser` real do `cli.py` (`_build_parser()`) e compara flags/required/dests dos 24 subcomandos — schema e CLI não podem divergir silenciosamente.
  - **Cobertura dos comandos:** 24 dos 25 subcomandos expostos. `init-data` BLOQUEADO no dashboard (`BLOCKED_COMMANDS`) por sobrescrever arquivos de dados (`data/`) — disparo acidental pela UI seria destrutivo; o comando continua disponível no terminal. O `--from-run` dos subcomandos de robustez/diagnóstico recebe dropdown de runs existentes (`path_run`), não texto livre.
  - **Restrição de escopo respeitada:** `cli.py` e `planet9lab/` ZERO modificações (verificado por `git status` antes do commit — só `dashboard/`, `tests/test_dashboard.py`, `pyproject.toml`, `.gitignore`). O dashboard só CHAMA (`python -m planet9lab.cli ...`) e SÓ LÊ runs.
  - **Bind:** `ui.run(..., host="127.0.0.1", port=8765, reload=False, show=False)` em `app.py` — nunca 0.0.0.0; teste automatizado assevera host/port.
  - **Leitura de runs (funcionalidades 3 e 4):** `runstore.py` lê EXCLUSIVAMENTE as pastas canônicas — `status.json` da raiz (nunca os duplicados), `results/ranking.csv` + `metrics_by_candidate.csv` + `candidates_evaluated.csv`, `audit/blockers.json` + `audit/run_manifest.json`, `diagnostics/*.json`; listagem com run_id, started/ended, status como badge e blockers ativos como alerta; relatório HTML por run com números VINDOS DOS ARQUIVOS (nenhum recálculo na camada de UI — único cálculo é formatação). `progress_info()` liga a barra de progresso aos checkpoints que o pipeline já grava (`checkpoints/` e `montecarlo_checkpoints/`, mesma fonte do `scripts/watch_progress.py`).
  - **Contrato científico verbatim (requisito não negociável):** `report.py` copia `caveats` e `interpretation` dos JSONs de diagnóstico NA ÍNTEGRA (mesma string, sem paráfrase/resumo/corte). Teste automatizado (`test_report_renders_caveats_and_interpretation_verbatim`) constrói uma run-fake com strings canário (aspas, acentos e `<tag>` para provar escape HTML sem cortar texto) e verifica SUBSTRING EXATA de cada caveat e da interpretation no HTML — teste no gate, não opcional. `test_real_run_report_contract` valida o mesmo contrato contra a run real `screen_20260903T211311606520Z` (4 caveats + interpretation do `selection_bias.json` literais no HTML).
- Requisito de runs longas (evidência das duas abordagens, conforme plano):
  - **Abordagem 1 — `subprocess.Popen` desacoplado (`runner.py`):** flags `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB` (com fallback sem breakaway se um job object do pai negar). Teste automatizado do ciclo completo de `launch()` + verificação prática fora dos testes: processo `sleep 20s` lançado via `_popen_detached`, pai encerrado imediatamente, processo FILHO confirmado VIVO após 5s (`tasklist /FI "PID eq ..."`, 2026-09-09 ~03:40Z, PID 2600 → `APPROACH1_ALIVE_AFTER_PARENT_EXIT True`). A run não depende da aba/navegador nem do processo da UI; o progresso acompanha-se por `status.json`/checkpoints (o job sobrevive e o dashboard relê o estado a cada refresh). **APROVADA — é a implementação entregue.**
  - **Abordagem 2 — `Start-Process` (processo de SO independente via PowerShell):** tentada na prática (2026-09-09 ~03:42Z; PID 12404 criado e confirmado no stdout de `Start-Process -PassThru`); FALHOU como implementação: 5s depois o processo não existia mais (`tasklist` → "nenhuma tarefa em execução correspondente"). Causa provável: má-passagem de argumentos com espaços no `-ArgumentList` (limitação conhecida) derruba o filho logo após o spawn. Documentada como exigido; NÃO bloqueia, pois a abordagem 1 atende.
- Testes — `tests/test_dashboard.py`: 15 novos (173 → 188), incluindo: fidelidade do schema vs parser real do CLI; `validate()` recusa caminho inexistente ANTES de spawnar (resolve relativos contra a raiz do repo); `build_argv` com posicionais e flags; ciclo completo do launcher (registro/estado do job em `.dashboard/jobs/`); `runstore` (blockers, status, checkpoint dirs, ignora duplicados da raiz); contrato verbatim (fake + run real); bind localhost.
- Gate (literal): `python -m pytest -q` → `188 passed in 80.61s`; `python -m ruff check .` → `All checks passed!` (1 erro I001 auto-fixável corrigido antes do commit; re-rodado limpo).
- Arquivos criados/alterados: `dashboard/` (8 módulos, novo), `tests/test_dashboard.py` (novo), `pyproject.toml` (+`nicegui`), `.gitignore` (+`.dashboard/`), `TASK.md` (esta entrada).
- Limitações honestas: (a) a subida REAL do servidor (`python -m dashboard`) não foi executada nesta sessão — a UI foi validada por testes unitários dos módulos; a validação visual cabe ao usuário com um comando local; (b) o dropdown de runs lista runs sob `runs/` — runs em outros `--run-root` não aparecem (o campo manual do formulário `path_run` cobre esses casos); (c) a barra de progresso é baseada em mtime/número de arquivos de checkpoint (mesma heurística do `watch_progress.py`), não em porcentagem real de integração.
- Vocabulário: nada nesta tarefa altera interpretação científica; o dashboard é instrumentação de operação (disparar/acompanhar/visualizar), sem recalcular números.
- Commit: `6249541` (código; 11 files, 1622 insertions) + commit docs desta entrada.
- Próximo passo: validação visual da UI pelo usuário (`python -m dashboard` → http://127.0.0.1:8765); Auditor decide — (a) projeção orbital→céu verdadeira (pendência do footprint), (b) Tarefa C (requer autorização explícita + benchmark na máquina que rodará), ou (c) refinamentos do dashboard apontados pelo uso real.



### 2026-09-09 12:56Z Cline (Executor) — Fechamento dos dois pontos pendentes da Tarefa D (autorização do Auditor)
- Status: concluído (validação visual real executada com evidência; caveat dinâmico corrigido com teste).
- **2. Caveat de sky coverage agora reporta o valor EFETIVO da config** — `planet9lab/selection_bias.py`: os dois ramos do caveat (footprint real / uniform_filling_factor) interpolam `effective_filling_factor` (`config.ossos_filling_factor`, com fallback `sky_coverage_deg2/41253` se None) formatado com 4 casas. O 0.9067 permanece no texto APENAS como proveniência do default ("0.9067 = mean across 2013A-E and 2013A-O blocks, the default this config may override; Bannister et al. 2016a"). Precisão dos números nos JSONs não muda — só o texto do caveat; interpretação científica intacta.
  - Teste novo `test_sky_coverage_caveat_reports_configured_filling_factor`: config com `ossos_filling_factor: 0.4848` → caveat contém "0.4848", NÃO contém "mean 0.9067" (padrão antigo não pode voltar) e contém "0.9067" (proveniência); config default → "0.9067 applied as uniform". Verificado que nenhum outro teste prendia o texto antigo.
- **1. Validação visual real (evidência, não só testes):**
  - **Servidor real:** `python -m dashboard` como processo de SO (Start-Process, PIDs 2756/3220, 2026-09-09 ~09:52-09:55Z). Subiu sem erro: stdout "Dashboard em http://127.0.0.1:8765 (bind exclusivo em localhost...)" + "NiceGUI ready to go on http://127.0.0.1:8765". HTTP real via Invoke-WebRequest: GET / → 200 (14.634 bytes), GET /launch → 200 (15.818), GET /jobs → 200 (13.481), GET /run/screen_20260903T211311606520Z → 200 (41.386), GET /rota-inexistente → 404 (roteamento real). Servidor parado após o teste (Stop-Process; nenhum processo remanescente).
  - **Render das 4 telas** via navegador simulado do NiceGUI (`nicegui.testing.User` 3.16.0, setup do plugin oficial: `prepare_simulation()` + lifespan; script em %TEMP%\_p9_visual_check.py) contra as runs REAIS do repositório — os builders executam de verdade (runstore/report/commands): TELA1 (/) listagem — título + run de referência visíveis (`should_see` OK, incl. conteúdo da tabela); TELA2 (/run/<id>) — relatório+progresso+"Blockers ativos" da run real renderizados sem exceção; TELA3 (/launch) — Select 'subcomando' com 24 opções (screen/montecarlo-scan/selection-bias-check/null-models conferidas) + form default (smoke) com campos e botão; TELA4 (/jobs) — abriu. Zero logs de ERROR durante todo o render. Saída: "VISUAL_VALIDATION: 4/4 telas renderizam sem erro".
  - **Erro de runtime encontrado e resolvido (do harness, não do dashboard):** a 1ª tentativa do script simulado quebrou com `AttributeError: AppConfig has no attribute 'markdown'` — o app ASGI do NiceGUI só fica completo após `ui.run()`/`add_run_config` (setup do plugin oficial). Replicado o setup canônico (`prepare_simulation()` + `lifespan_context`) e o render passou 4/4; o dashboard em si nunca errou (a subida real acima confirma).
  - Nota honesta: a interação de TROCAR o subcomando no Select não é simulável pelo usuário fake (dropdown do QSelect é render client-side); o rebuild usa o mesmo `_command_form` executado no build da página, e as options conferidas vêm das props server-side do elemento. Troca real = interação de navegador do usuário.
- **Observação para o Auditor (não agí):** a entrada da Tarefa D (03:45Z) foi editada externamente nesta árvore para "00:45Z" — 00:45 é o horário LOCAL (BRT) do registro original em UTC; com sufixo "Z" o valor tecnicamente correto seria 03:45Z. PRESERVEI a edição (nada de histórico é apagado), commit inclui a mudança explicitamente; decisão final do padrão de timestamp fica com o Auditor.
- Arquivos alterados: `planet9lab/selection_bias.py` (caveat dinâmico), `tests/test_selection_bias.py` (+1 teste, 188 → 189), `TASK.md` (esta entrada + edição externa do timestamp preservada).
- Gate (literal, pós-mudança): `python -m pytest -q` → `189 passed in 90.49s`; `python -m ruff check .` → `All checks passed!`.
- Vocabulário: nada altera interpretação científica (texto de caveat e instrumentação de operação apenas).
- Próximo passo: decisões já registradas no Log anterior (projeção orbital→céu, Tarefa C com autorização explícita, refinamentos por uso real do dashboard).

### 2026-09-09 13:29Z Cline (Executor) — Item (b): execução OFICIAL do selection-bias-check com config corrigida sobre a run de referência
- Status: concluído (nenhum código novo; comando existente rodado contra a run real; artefato de referência substituído conforme autorização).
- **Run escolhida (passo 1, justificativa):** `screen_20260903T211311606520Z`. Inventário de `runs/`: 2 `montecarlo_*` (não são screening de candidatos; descartadas), 2 `screen_*` de budget `low` (50 yr, 5 candidatos — descartadas por budget menor) e 2 `screen_*` de budget `medium` (200 yr, 8 candidatos): `204018` tem apenas **14 ETNOs** incluídos (precedeu a validação final do catálogo; sem `diagnostics/`) e `211311` tem **16 ETNOs**, replay `python main.py screen --budget configs/budgets/medium.yaml --seed 12345 --candidates data/candidates_quadro2.csv --etnos data/etnos/catalog_validated.csv`, é a mais recente e a referência já citada em TASK.md/docs/LIMITACOES.md, além de já portar o artefato de bias-check anterior. Legítima e mais atual.
- **Segurança:** artefato antigo copiado antes da sobrescrita para `%TEMP%\p9_bias_recheck\selection_bias_OFFICIAL_PRE_20260909.json` (runs/ é gitignored — sem backup seria irrecuperável). Snapshot de `blockers.json` antes/depois idem.
- **Execução oficial (passo 2):** `python main.py selection-bias-check --from-run runs\screen_20260903T211311606520Z` — config canônica (`ossos_filling_factor: 0.9067`, `use_ossos_footprint: false` → modo `uniform_filling_factor`; footprint real permanece para o item (a), que depende da projeção orbital→céu não implementada). Novo artefato gravado em `runs/<rid>/diagnostics/selection_bias.json` (evento `selection_bias_check_completed` em 2026-09-09T13:23:01Z no `events.log`).
- **Números oficiais (passo 3):** `real_catalog_resultant_length_R = 0,299836`; `surviving_synthetic_resultant_length_R = 0,032567`; `real_exceeds_synthetic_R = true`; `surviving_fraction = 0,1918` (959/5000 sintéticos sobreviventes); `bias_model = h_prior_from_catalog` (16 H do SBDB, mediana 6.465); `n_real_catalog = 16`; `ossos_footprint_mode = uniform_filling_factor`. **Caveats na íntegra (verbatim do JSON):** (1) "Modelo angle-only (omega, Omega, M): nao modela geometria de footprint real nem cadencia real do survey."; (2) "Depth efficiency: OSSOS quadratic-logistic curve (Bannister et al. 2018, ApJS 236:18) evaluated at V = H + 5 log10(r·Delta) per-object, when distances are available; H-only linear stand-in otherwise."; (3) "Sky coverage: OSSOS filling factor 0.9067 applied as uniform per-object survival probability (0.9067 = mean across 2013A-E and 2013A-O blocks, the default this config may override; Bannister et al. 2016a; angle-only population has no sky-plane position)." — nota: já usa o caveat DINÂMICO do commit `cae0958`, agora validado em execução real; (4) "Resultado NAO deve ser citado como probabilidade de deteccao calibrada - e um teste de plausibilidade qualitativo.". `interpretation`: "O catalogo real tem concentracao angular (R) maior que a populacao sintetica sujeita ao mesmo modelo de selecao — o clustering real NAO e trivialmente explicado por vies de selecao neste modelo simplificado."
- **Comparação com o resultado antigo (passo 4):** artefato pré-oficial (2026-09-04, fallback ≈0,485, modelo angle-only da época): R_sint 0,00593; 1742/5000 (0,3484); `real_exceeds_synthetic_R = true`. Oficial agora: R_sint 0,032567 (≈5,5× maior), sobrevivência 0,1918, `real_exceeds_synthetic_R = true` — **conclusão central MANTIDA em execução oficial** (não apenas na verificação isolada de ontem). R_real inalterado (0,299836; propriedade do catálogo). Razão R_real/R_sint cai de ≈50× (antigo, inflada pelo modelo mais restritivo) para ≈9,2× — o modelo corrigido explica mais clustering, porém ainda insuficiente para trivializar o observado. Determinismo cross-check: números idênticos aos da verificação de ontem contra o esqueleto em %TEMP% (mesma seed/catálogo por caminhos de resolução distintos).
- **Blockers (passo 5):** antes = depois = só `etno_catalog_not_fully_validated` (science_limit). O `no_observational_bias_model` NÃO estava presente (removido em 2026-09-04T16:51:21Z — evento `no_observational_bias_model_blocker_removed` visível no histórico do `events.log`), logo a remoção automática da Tarefa A não tinha o que remover nesta execução: comportamento idempotente confirmado correto.
- **Nova referência oficial (passo 6):** o artefato em `runs/screen_20260903T211311606520Z/diagnostics/selection_bias.json` (2026-09-09T13:23Z) SUBSTITUI o antigo como resultado válido daqui pra frente; qualquer citação futura dos números de bias-check deve usar os valores desta entrada. Apontamento em "Bloqueios" (B2): atualização do artigo PRONTA para preparação caso o Auditor julgue necessário, exigindo autorização explícita separada — **nenhum .docx foi tocado**.
- Arquivos alterados: apenas `TASK.md` (B2 + esta entrada). Artefatos de run (`runs/...`) são gitignored e não entram no commit.
- Gate (literal, inalterado — validação de continuidade): `python -m pytest -q` → `189 passed in 79.95s`; `python -m ruff check .` → `All checks passed!`.
- Vocabulário: nada confirma nem descarta candidato; o resultado é de triagem exploratória dentro do protocolo ("clustering real não é trivialmente explicado por este modelo de viés simplificado").
- Commit: docs (B2 + esta entrada).

- Próximo passo: Auditor decide — (i) autorizar (ou não) atualização do artigo com os números oficiais (B2), (ii) item (a) do plano (projeção orbital→céu para habilitar o footprint real), ou (iii) Tarefa C (autorização explícita + benchmark na máquina de execução).

### [2026-09-09 17:07Z] Cline (Executor) — PC: ALUNOSENAI — NOTA DE CONVENÇÃO: identificação de máquina no Log
- Status: concluído
- O que foi feito / resultado real: a partir desta entrada, TODAS as entradas do Log de execução passam a incluir identificação de máquina no cabeçalho, no campo `<PC: ...>` (valor de `$env:COMPUTERNAME` do Windows). Entradas anteriores a esta NÃO têm esse campo porque a convenção não existia ainda — não inferir de qual máquina vieram sem evidência explícita (algumas mencionam H:\, outras D:\, o que já é um indício indireto, mas não conclusivo). Hostname deste PC: ALUNOSENAI.
- Commit: pendente
- Próximo passo: manter o campo `<PC: ...>` em todas as entradas futuras, deste PC ou de outro.
- PC: ALUNOSENAI

### 2026-09-10 00:23Z Cline (Executor) — PC: LURIAT — PASSO 2: atualização do artigo v2 com os números oficiais (autorização B2)
- Status: concluído (6 substituições aplicadas + 1 correção de resíduo; artigo em `docs/PLANET9_ARTIGO_v2_ABNT.docx`; nenhum código-fonte alterado).
- **Contexto:** Auditor aprovou na seção "Bloqueios" (B2) a atualização do artigo com os números oficiais do selection-bias-check (`screen_20260903T211311606520Z`, 2026-09-09T13:23Z). PASSO 0 (confirmação read-only) e PASSO 1 (proposta de texto A/B/C/D) já reportados/aprovados anteriormente.
- **Edições aplicadas (todas via substituição textual exata; estilo/formatação ABNT preservados — fontes, espaçamento, negrito/itaílico mantidos nos parágrafos tocados):**
  - A — **RESUMO (L6):** `0,00593` (antigo) → `0,032567` (novo R_sintético sobrevivente).
  - B — **§3.4 título (L65):** `Modelo de viés de seleção observacional: resultado inicial` → `Modelo de viés de seleção observacional: resultado` (remoção de "inicial").
  - C — **§2.9 (L42 e L45):** `149 testes` → `189 testes`; texto de procedimento atualizado para `19,18% (959 de 5.000)` e adicionada nota entre parênteses sobre o footprint real (`cujo filtro posicional permanece desligado por padrão, com posição sintética sendo um proxy uniforme em céu, não uma projeção orbital→céu verdadeira`).
  - D — **§3.4 ¶1 (L66):** `34,84%` + `0,00593` → `19,18% (959 de 5.000)` + `0,032567`; trecho completo reescrito para `a fração sobrevivente ao filtro de seleção foi de 19,18% (959 de 5.000), com modelo de viés h_prior_from_catalog (H reais de 16 objetos via JPL SBDB, mediana 6,465; eficiência de detecção OSSOS Bannister et al. 2018, ApJS 236:18). Sobre essa subpopulação sobrevivente, a estatística R de Rayleigh (semente 12345) resultou em R ≈ 0,032567 — ≈9,2× abaixo do catálogo real e ainda essencialmente uniforme, sem concentração angular detectável —, contra R = 0,299836 do catálogo real de 16 objetos.`
  - E — **§3.4 ¶2 (L67):** adicionada a mesma nota entre parênteses sobre footprint real na enumeração de limitações.
  - F — **§3.5 (L70):** `149 testes` → `189 testes`.
  - G — **CORREÇÃO DE RESÍDUO (L46, §2.9):** após as substituições principais, verificação automatizada detectou `34,84%` remanescente no parágrafo de procedimento → substituído por `19,18% — 959 de 5.000`.
- **Releitura pós-edição (PASSO 3):** verificação automatizada (Python `python-docx`) confirmou — **nenhum número antigo restante** (`0,00593`, `0,3484`, `34,84%`, `149 testes` todos limpos) e **todos os números oficiais presentes** (`0,032567`, `19,18%`, `189 testes`, `0,299836`, `9,2`). §3.4 ¶3 e §3.5 permaneceram intactas (já confirmado que não precisavam mudar). Nenhuma referência cruzada quebrada detectada.
- **Observação sobre `0,1918`:** o número `0,1918` (fração decimal) não aparece no texto — em seu lugar, usa-se `19,18% (959 de 5.000)` (formato percentual + contagem), decisão de estilo consistente entre L46 e L66. Não é ausência indevida.
- **Pendência de ambiente (não bloqueante, registrada para não se perder):** durante esta sessão, `.venv\pyvenv.cfg` apontava para `C:\Users\AllunoSenai\...` (erro de caminho entre PCs). Gate passou pela rota alternativa (`H:\planet9-screening-lab\.venv\Scripts\python.exe` direto). O `pyvenv.cfg` foi corrigido localmente para `C:\Users\lucas\AppData\Local\Programs\Python\Python311\python.exe`, mas **essa correção de ambiente NÃO está neste commit** — `.venv\` é gitignored (`.gitignore:32 .venv/`). Se o venv vier a ser recriado em qualquer das máquinas, garantir que o `pyvenv.cfg` aponte para o Python correto daquela máquina antes de rodar o gate.
- Arquivos alterados: `docs/PLANET9_ARTIGO_v2_ABNT.docx` (novo, untracked → adicionado) + `TASK.md` (esta entrada).
- Gate (literal): `python -m pytest -q` → `189 passed in 79.97s`; `python -m ruff check .` → `All checks passed!`.
- Vocabulário: mantido o tom conservador aprovado (sem "confirma" nem "descarta" viés de seleção; "clustering real não é trivialmente explicado por este modelo de viés simplificado").
- Commit: docs (artigo v2 atualizado + entrada no Log; B2 do Auditor).
- Próximo passo: Auditor decide — (i) item (a) do plano (projeção orbital→céu para habilitar o footprint real) ou (ii) Tarefa C (autorização explícita + benchmark na máquina de execução). Artigo atualizado; sem pendências de escrita imediatas.
- PC: LURIAT
