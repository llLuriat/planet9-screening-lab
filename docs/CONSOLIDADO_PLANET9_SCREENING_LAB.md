# Consolidado unico - Planet9 Screening Lab

Data de consolidacao: 2026-08-14

Este arquivo substitui a mistura de zips, prompts, relatorios parciais e resumos de chat como ponto unico de retomada do projeto. Ele nao e um dump historico: e uma sintese operacional do que existe, do que foi corrigido, do que ainda e decisao cientifica e da proxima ordem recomendada.

## 1. Fontes consolidadas

Fontes analisadas nesta consolidacao:

- GitHub: `https://github.com/llLuriat/planet9-screening-lab.git`
- Zip recebido: `C:\Users\Luriat\Downloads\tudo.zip`
- Conteudo de `tudo.zip`:
  - `workspace.zip`: projeto completo evoluido, com codigo, docs, testes, runs e artigo.
  - `cont.zip`: contexto bruto de chat (`contexto.txt`, `camacoCONTEXTO.txt`).
  - `filesPRA.zip`: roteiro, auditoria e prompt de correcao pos-Auditoria V3.

Estado observado:

- A pasta atual `C:\Users\Luriat\Documents\simuladorV2` estava praticamente vazia, com apenas `.git` local sem commits e sem remote.
- O clone temporario do GitHub tem 3 commits recentes:
  - `59cf652 docs: guia de setup do zero, ordem completa de comandos`
  - `9d13715 docs: valida integration_years=4e9 em secular.yaml via benchmark de hardware; corrige LIMITACOES.md desatualizado`
  - `d6dcc0d fix: isola testes de runs/ real, arquiva paramscan.py morto, sincroniza root-copies via helper unico`
- O `workspace.zip` contem uma evolucao maior que o GitHub: 212 arquivos contra 84 arquivos no clone, incluindo docs historicos, artigo revisado, testes adicionais, runs reais de 1 Myr, `pycache`, artefatos e um zip interno antigo.

Conclusao pratica: o GitHub e a base publica limpa; `workspace.zip` e o estado evoluido nao commitado; os outros zips sao memoria de contexto. A proxima acao deve partir do `workspace.zip`, mas com higiene antes de commitar.

## 2. Veredito atual

O projeto saiu de "artigo prometendo mais do que o codigo executou" para um estado mais honesto:

- Os achados da Auditoria V3 foram tratados no estado de `workspace.zip`.
- Os bugs tecnicos principais foram corrigidos.
- O artigo foi reescrito para nao alegar runs seculares/Gyr que nao existem.
- Permanecem pendencias cientificas explicitas, especialmente run secular, estabilidade entre seeds, catalogo ETNO validado externamente e estrategia de versionamento de `runs/`.

Veredito herdado do relatorio no zip:

`ACCEPTED_WITH_WARNINGS`

Isto significa: codigo e documentacao estao muito melhores, mas ainda nao existe lastro numerico para alegar estabilidade secular/Gyr como resultado final.

## 3. O que ja foi corrigido no estado do zip

### Auditoria V3 - correcoes tecnicas

O relatorio `docs/historico/RELATORIO_CORRECAO_AUDITORIA_V3.md` registra os 13 achados tratados.

Itens ja corrigidos:

- `P0-2`: `load_candidates` deixou de truncar silenciosamente pela ordem do CSV. Agora ordena por `candidate_id`, registra candidatos excluidos por limite de capacidade e grava isso em manifest.
- `P1-1`: `--seed` foi documentado como inerte para `screen`/`compare` com catalogo fixo; manifest inclui `seed_effect`.
- `P1-4`: `weak_delta_floor` foi removido dos YAMLs de scoring porque era campo morto.
- `P1-5`: thresholds `1e-4` e `1e-3` viraram constantes nomeadas e documentadas em `metrics.py`.
- `P1-6`: `doctor.py` passou a verificar se o caminho apontado por `runs/latest_run.txt` realmente existe.
- `P2-1`: configuracao do `ruff` foi fixada explicitamente no `pyproject.toml` e os erros reportados foram tratados.
- `P2-2`: `LIMITACOES.md` foi atualizado para reconhecer que os candidatos do Quadro 2 ja foram incorporados.
- `P2-3`: `--run-root` foi exposto no CLI para `screen`, `compare`, `smoke` e `montecarlo-scan`.
- `P2-5`: testes de regressao foram adicionados para os cenarios da auditoria.

Itens finais tratados depois:

- `P1-3`: `anti_alignment_score` foi renomeado/documentado como media angular normalizada, preservando compatibilidade e valores publicados.
- `P2-4`: foi adicionado blocker consultivo para regime de inclinacao nao validado (`i_deg >= 80`), sem invalidar automaticamente a run.
- `P0-1`: o artigo `docs/Artigo_FEBRACE_revisado.docx` foi reescrito para refletir apenas execucoes reais de 1 Myr, nao resultados seculares/Gyr inexistentes.
- `P1-2`: estabilidade entre seeds permaneceu como limitacao explicita, sem falsa validacao.

Gate final registrado no relatorio do zip:

- `python3 -m pytest -q`: 116 passed
- `python3 -m ruff check . --no-cache`: passed
- `python3 main.py doctor`: passed
- abertura do `.docx` via `python-docx`: passed

Observacao: estes resultados foram herdados do relatorio incluido no zip. Antes de commitar, devem ser reexecutados na maquina atual depois de limpar/importar o workspace.

## 4. O que foi realmente executado cientificamente

Runs reais presentes no `workspace.zip`:

- `runs/experiment_angle_robustness_20260812T145545073924Z`
- `runs/experiment_i_boundary_scan_20260812T145800363579Z`

Escopo real dessas runs:

- horizonte curto: 1 Myr;
- REBOUND real, sem fallback analitico;
- experimentos de sensibilidade, nao validacao secular final;
- cobertura principal: variacao de `omega9` para o candidato preferido `row6` e varredura de inclinacao em torno da linha `row4`.

O que nao existe ainda:

- nenhuma run real de `secular.yaml` com `1e8` anos;
- nenhuma run de 1-4 Gyr;
- nenhuma validacao real das 7 linhas do Quadro 2 em escala secular;
- nenhuma estabilidade entre multiplas seeds;
- nenhum cruzamento externo campo-a-campo dos 13 ETNOs contra a Tabela A1 de De la Fuente Marcos & De la Fuente Marcos 2014;
- nenhum modelo de vies observacional implementado.

Regra de honestidade para artigo/apresentacao:

Nao afirmar estabilidade secular, tempo de ejecao, sobrevivencia por Gyr, alinhamento percentual ou efeito em nuvem de Oort como resultado executado ate que exista uma run correspondente com manifest e artefatos.

## 5. Achados novos do ultimo chat

O resumo mais recente do chat trouxe melhorias alem da Auditoria V3. Elas ainda nao estao implementadas, exceto quando indicado.

### 5.1 Paralelizacao

Maior ganho pratico de curto prazo.

Status: IMPLEMENTADA em 2026-08-15 (Etapa 1 do PROMPT_EXECUCAO_PLANET9).

Locais identificados:

- `planet9lab/run.py`: `_run_candidates_and_finalize`, loop sequencial por candidato.
- Cada candidato roda dois branches independentes: com P9 e sem P9.
- `planet9lab/montecarlo.py`: loops sequenciais nos estagios 2 e 3.
- `planet9lab/robustness.py`: loops independentes em leave-one-out, convergence, validate_top e null_models.

Diagnostico:

- Cada branch cria uma nova `Simulation()`.
- Nao ha estado global fisico compartilhado.
- Checkpoints sao por `candidate_id`.
- Portanto, ha paralelizacao segura por processo.

Cuidado importante:

- `save_candidate_to_cache` e `write_csv(status_path)` escrevem arquivos compartilhados dentro do loop.
- O desenho seguro e: workers retornam payloads; processo pai escreve cache/status/CSV em ordem deterministica.
- A ordenacao final de ranking ja e deterministica (`rows.sort(...)`), entao a paralelizacao nao precisa mudar os numeros, so o tempo de parede.

Como foi implementado (Etapa 1):

- Novo modulo `planet9lab/parallel.py`: `run_parallel_map` (stdlib `concurrent.futures.ProcessPoolExecutor`), com `max_workers` configuravel (arg ou env `PLANET9_MAX_WORKERS`), ordem de entrada preservada e fallback sequencial automatico se o pool nao puder ser criado.
- `_run_candidates_and_finalize`: workers retornam payloads puros; o pai escreve cache/status/CSV/eventos em ordem de candidato. Checkpoints REBOUND sao por `candidate_id`, entao workers nunca escrevem arquivo compartilhado.
- Aplicado em `execute_run`, `run_compare`, `run_smoke`, `run_screen`, `resume_run`, `run_montecarlo_scan` (parametro `max_workers`).
- Aplicado em `planet9lab/montecarlo.py` (estagios 2 e 3) e `planet9lab/robustness.py` (leave-one-out, convergence, validate_top, null_models). No null_models, os draws de RNG (`build_null_etnos`) ficam no processo pai em ordem, para a sequencia aleatoria ser identica a da versao sequencial.
- CLI: `--max-workers` exposto em screen/compare/smoke/resume/montecarlo-scan/leave-one-out/convergence/validate-top/null-models.
- Testes: `tests/test_parallel.py` (7 testes) - sequencial vs paralelo em `low.yaml` byte-identico em ranking, metricas, ordem de candidatos, cache e manifests; montecarlo estagios 2/3 e robustez byte-identicos (budget secular stubado com `low.yaml` para nao rodar integracao secular); utilidade `run_parallel_map` preserva ordem e fallback roda initializer.

Recomendacao:

Implementar primeiro. E a melhoria com melhor relacao impacto/risco porque reduz tempo sem mudar fisica.

### 5.2 `exact_finish_time`

Inconsistencia confirmada:

- `_run_rebound` usa o default do REBOUND, equivalente a `exact_finish_time=1`.
- `run_branch_checkpointed` usa `exact_finish_time=0`.

Recomendacao:

Padronizar `sim.integrate(..., exact_finish_time=0)` tambem no caminho nao checkpointado. E alteracao pequena, coerente com o caminho secular/checkpointado e com o benchmark existente.

Classificacao:

Categoria A tecnica, mas muda levemente trajetorias numericas por consistencia de integracao. Deve ter teste de regressao focado.

Status: IMPLEMENTADA em 2026-08-15 (Etapa 2 do PROMPT_EXECUCAO_PLANET9).

Como foi implementado (Etapa 2):

- `planet9lab/engine.py::_run_rebound` agora integra com `sim.integrate(..., exact_finish_time=0)`, igual a `run_branch_checkpointed` e a `scripts/benchmark_integration_cost.py`. `physics.py` e `doctor.py` fazem integracao de sanidade de 1 ano (fora do escopo de screening) e nao foram alterados.
- Testes: `tests/test_exact_finish_time.py` (2 testes) - prova que `_run_rebound` agora e bit-identico a uma integracao explicita `exact_finish_time=0`; mede e documenta a magnitude do delta contra o default antigo (=1).

Impacto numerico medido (budget nao-alinhado: integration_years=100 yr, timestep=0.593644 yr, mesmos dados de `data/`):

- `|delta energy_drift_rel| ~= 1.6e-07` (drift de 3.42e-07 no default antigo para 1.80e-07 com `exact_finish_time=0`);
- `delta t_final ~= 0.33 yr` (o default antigo trunca o ultimo passo para parar exatamente em 100.0 yr; o padronizado para no proximo boundary de passo, 100.326 yr);
- em budget alinhado (`low.yaml`: 50 yr / 0.5 yr = passos inteiros) o delta e exatamente zero, porque o default ja terminava no mesmo boundary.

Gate p/ Etapa 2: 125 passed (era 123), ruff limpo, doctor ok.

### 5.3 WHFast corrector

Informacao corrigida:

- Em REBOUND 5.1.1, nao existe `sim.safe_mode` nem `sim.ri_whfast` como citado em contexto anterior.
- A forma correta observada e `sim.integrator.corrector = 17`.
- Default atual e `0`.

Recomendacao:

Nao ativar automaticamente no mesmo commit da paralelizacao. Deixar opcao configuravel ou fazer um commit separado com comparacao de drift/score, porque altera levemente resultados.

Classificacao:

Categoria B leve: decisao metodologica/numerica, embora tecnicamente simples.

### 5.4 MEGNO

Informacao corrigida:

- Em REBOUND 5.1.1 existe `sim.init_megno(seed=...)`.
- Nao existe `init_megno_seed` nesta versao.
- A seed fixa e possivel via argumento `seed`.

Valor cientifico:

- MEGNO pode funcionar como indicador rapido de caos.
- Pode ajudar a conectar integracoes curtas com estabilidade de longo prazo, desde que calibrado contra algumas runs longas reais.
- Tambem seria feature util para futuro surrogate/ML.

Recomendacao:

Preparar infraestrutura opcional, mas nao usar MEGNO como prova de estabilidade Gyr no artigo sem calibracao. Implementar depois da paralelizacao e da consistencia `exact_finish_time`, porque indicador de caos e sensivel a ruido numerico.

Status: IMPLEMENTADA em 2026-08-15 (Etapa 4 do PROMPT_EXECUCAO_PLANET9).

Como foi implementado (Etapa 4):

- Novo modulo `planet9lab/megno.py`: `run_megno(engine, etnos, candidate, integration_years, seed=42)` usa `sim.init_megno(seed=...)` (API do REBOUND 5.1.1; nao existe `init_megno_seed` nesta versao, e `sim.megno` e um metodo, nao propriedade). Reusa `ReboundEngine._configure_sim` para condicoes iniciais e integrator identicos ao funil. Resultado e o `<Y>` do MEGNO com seed fixa, mais um `interpretation_hint` deixando explicito que e indicador auxiliar nao calibrado.
- CLI: subcomando `megno` (isolado, nao toca no funil) com `--candidate`, `--budget`, `--years`, `--seed` (default 42), `--allow-analytical-fallback`.
- NENHUM modulo do funil (`run.py`, `engine.py`, `montecarlo.py`, `robustness.py`, `parallel.py`) referencia MEGNO - garantido por teste de isolamento.
- Testes: `tests/test_megno.py` (5 testes) - valor finito com seed fixa; reproducibilidade bit-exata com a mesma seed; sensibilidade a seed (medido: 1.7746 com seed 42 vs 2.0930 com seed 43 em `low.yaml`); sistema 2-corpos regular devolve MEGNO ~2.0 (1.5-2.5); isolamento do funil via leitura de fonte.
- Restricao 1 respeitada: integracao apenas com `configs/budgets/low.yaml` (50 yr); nenhuma integracao secular disparada.
- IMPORTANTE: usar MEGNO como argumento de estabilidade Gyr no artigo e Categoria B - pare e pergunte ao usuario antes, nao implemente silenciosamente.

Gate p/ Etapa 4: 130 passed (era 125), ruff limpo, doctor ok.

### 5.5 Rayleigh Z / Kuiper

Valor:

- Substitui thresholds ad hoc por p-valores/estatistica circular mais defensavel.
- Destrava analise de poder: quantos ETNOs seriam necessarios para confirmar/refutar a hipotese com confianca.

Recomendacao:

Boa melhoria metodologica, mas nao deve ser misturada com os fixes de performance/numerica. Fazer depois que os artefatos atuais estiverem versionados e os resultados seculares estiverem mais claros.

Status: IMPLEMENTADA COMO OPCIONAL em 2026-08-15 (Etapa 5 do PROMPT_EXECUCAO_PLANET9). Nao promovida a padrao e nenhum candidato existente foi reclassificado.

Como foi implementado (Etapa 5):

- Novo modulo `planet9lab/circular_tests.py` (stdlib, sem scipy): `rayleigh_z` (Z = n*R^2, p com correcao de Zar 1999), `kuiper_v` (estatistica V com V* e p por interpolacao da tabela de Stephens 1970), `rayleigh_power` (potencia via chi-quadrado nao-central assintotica, seed fixa) e `required_n_for_rayleigh_power` (menor n para potencia alvo).
- Novo `planet9lab/circular_report.py` + subcomando CLI `circular-stats --from-run <run> [--alpha 0.05]`: relatorio READ-ONLY que deriva o Rayleigh de cada candidato a partir do `apsidal_clustering_R` ja armazenado (Z = n*R^2, n do manifest da run) e roda Rayleigh/Kuiper sobre o catalogo observado usado pela run; nunca escreve no run e nunca reclassifica.
- `--alpha` e a unica opcao; o criterio atual (pesos ad hoc) permanece o default.
- Testes: `tests/test_circular_stats.py` (9 testes) - uniforme p alto vs aglomerado p baixo (Rayleigh e Kuiper); derivacao do R armazenado consistente com o caminho direto; p em [0,1] e determinismo; potencia monotona em n e rho; n requerido cresce quando rho cai; relatorio sobre as duas runs reais e READ-ONLY (bytes do run identicos antes/depois) e usa n=13 do manifest.

Comparacao lado a lado sobre as runs reais (ambas, mesmo catalogo, n=13):

- Catalogo observado (`catalog_validated.csv`, 13 ETNOs, varpi reconstituidos do manifest): Rayleigh R=0.365, Z=1.73, p=0.178; Kuiper V*=1.46, p=1.0 -> cluster NAO significativo a alfa=0.05.
- Os 5 candidatos `candidate_of_interest` de cada run (10 no total): Rayleigh p entre 0.16 e 0.18 com P9 -> NENHUM significativo a alfa=0.05.
- Analise de poder (alfa=0.05, potencia 80%): n requerido ~107 para rho=0.3, ~39 para rho=0.5, ~20 para rho=0.7. O catalogo atual (n=13) esta muito abaixo do necessario para detectar rho=0.5 com 80% de potencia.

Categoria B (decidido em 2026-08-15, autorizado pelo usuario: MANTER AD HOC COMO DEFAULT):

- A comparacao sugere que o criterio ad hoc atual e mais leniente que Rayleigh/Kuiper a alfa=0.05: 5/5 candidatos de interesse por run deixariam de ser significativos. Opcoes avaliadas: (a) manter threshold ad hoc como default e usar Rayleigh/Kuiper apenas como diagnostico; (b) promover Rayleigh a criterio com novo alpha calibrado; (c) usar poder estatistico para justificar ampliar o catalogo antes de decidir.
- DECISAO: opcao (a). Rayleigh/Kuiper permanecem como opcao configuravel read-only (`circular-stats`); nenhum candidato existente foi reclassificado e o criterio ad hoc continua sendo o default do funil. Reabrir a discussao (b) ou (c) exigira nova autorizacao explicita e, no caso de (b), recalibracao de alpha e re-execucao do funil.

Gate p/ Etapa 5: 139 passed (era 130), ruff limpo, doctor ok.

### 5.6 Mare galactica/passagens estelares

Diagnostico:

- Literatura usa esses efeitos em simulacoes de TNOs distantes.
- Para semi-eixos abaixo de cerca de 1000 UA, efeito tende a ser fraco no escopo deste projeto.

Recomendacao:

Documentar como limitacao/robustez futura. Nao priorizar implementacao agora.

### 5.7 Estagio 4 secular e Estagio 5 detectabilidade

Estado:

- O funil ainda declara partes `not_implemented`.
- Estagio 4 exigiria formalismo secular tipo Hamiltoniano quadrupolo/octupolo.
- Estagio 5 exigiria modelo de detectabilidade/fotometria/cobertura de survey.

Recomendacao:

Manter como trabalho futuro ate haver run secular real e objetivos de submissao claros.

### 5.8 Fechamento da Tarefa 1 (LIMITACOES + artigo) — 2026-08-15

Reconciliacao das tres localizacoes (`docs/LIMITACOES.md`,
`docs/Artigo_FEBRACE_revisado.docx`, este CONSOLIDADO):

- `docs/LIMITACOES.md` atualizado para o estado real: benchmark existe com
  proveniencia sandbox (nao referencia de prazo); leave-one-out, null-models e
  QMC marcados como RESOLVIDO/PARCIAL (implementados, nao executados nas runs
  reais); rastreabilidade artigo<->run (item 4) confirmada ausente;
  fechamento registra MEGNO/Rayleigh-Kuiper opcionais e a decisao Categoria B
  de manter threshold ad hoc como default.
- `docs/Artigo_FEBRACE_revisado.docx`: verificado consistente com as runs reais
  (alega so as duas runs de 1 Myr; Tabela 2 marca "Nao executado"; S9
  qualitativo sobre ω9/Ω9/M0). Sem alteracao de conteudo (qualquer mudanca de
  claim e Categoria B).
- PENDENCIA levantada no fechamento: os percentuais da Tabela 4 do artigo
  (~45%/28%/15%/8%/3-5%) nao tem artefato de run
  (`results/parameter_space_scan.csv` e `reduction_funnel_summary.json`
  ausentes do repo e do git). Categoria B pendente: marcar como estimativa do
  modelo ou rodar o scan.
- PENDENCIA Categoria B: proveniencia de ω9/Ω9/M0 (ver 5.8a e
  `docs/CANDIDATOS_QUADRO2.md`).

Gate do fechamento: pytest 139 passed, ruff limpo, doctor ok, docx abre via python-docx.

### 5.8a Execucao do scan real para a Tabela 4/funil — 2026-08-16 (autorizada)

Autorizacao explicita da sessao (opcao 2 do dimensionamento): rodar o scan
completo com `max_stage3_samples` reduzido de 60 para 2 para caber em
minutos no sandbox de 2 nucleos.

- Config: `configs/montecarlo/parameter_space.yaml` (QMC Halton, N=20.000,
  seed 20260727, bounds [M5-20, a380-980, e0.1-0.8, i0-40];
  `max_stage2_samples: 200`, `max_stage3_samples: 2`).
- Custo calibrado na maquina: ~14 s/Myr com 13 ETNOs (calibracao
  /tmp/calib_stage3.py) -> ~23 min/ramo em 1e8 yr; scan completo ~30 min.
- Run real: `runs/montecarlo_20260816T001216569981Z/` com artefatos
  `results/parameter_space_scan.csv` (20.000 linhas) e
  `results/reduction_funnel_summary.json` (run_manifest com hashes da config,
  catalogo e gigantes).
- Resultado do funil real: Estagio 0 (bounds fisicos) 20.000/20.000 pass;
  Estagio 1 (separacao de Hill) 20.000/20.000 pass; Estagio 2 (estabilidade
  N-corpos 1 Myr) 200/200 pass (100% dos avaliados; 1,0% do total);
  Estagio 3 (alinhamento apsidal secular 1e8 yr) 2/2 pass (100% dos
  avaliados; 0,01% do total). Estagios 4/5: `not_implemented`.
- O funil real NAO reproduz os percentuais estimados (~45/28/15/8/3-5%): todos
  os pontos avaliados passaram em todos os estagios implementados; os valores
  de "volume restante" (1,0%/0,01%) refletem o limite de capacidade amostral,
  nao eliminacao fisica. Poder estatistico com a amostra reduzida de Estagio 3
  NAO recalculado (mesma honestidade do Rayleigh/Kuiper).
- Artigo atualizado (`docs/Artigo_FEBRACE_revisado.docx`): Tabela 5 (funil,
  docx table index 4) reescrita com os valores reais e nota explicita de
  Estagio 3 com 2 ramos (vs 60 configurados); Seção 7 (paragrafos 44, 46, 47)
  reescrita citando o artefato `runs/montecarlo_20260816T001216569981Z/results/`
  e registrando que os percentuais antigos eram estimativa sem artefato.
- `docs/LIMITACOES.md` atualizado: pendencia do funil marcada RESOLVIDO com
  a amostra reduzida documentada e o poder estatistico nao recalculado.
- Para o scan completo (60 ramos no Estagio 3, ~horas) e necessaria nova
  autorizacao explicita.

Gate 5.8a: pytest 139+ passed, ruff limpo, doctor ok, docx abre via python-docx.

## 6. Prioridade recomendada daqui para frente

### Prioridade 0 - arrumar a casa antes de codar

Status: CONCLUIDA em 2026-08-15 (Etapa 0 do PROMPT_EXECUCAO_PLANET9).

1. Workspace importado de forma limpa em `/workspace` a partir dos zips consolidados (arvore unica, sem o diretorio `workspace/` aninhado e sem `__pycache__`).
2. Fora de versionamento: `__pycache__/`, `*.py[cod]`, `*.zip` (`.gitignore`); os 4 zips-fonte foram removidos do indice git (mantidos em disco, nao rastreados).
3. `.gitignore` cobrindo `__pycache__/`, `*.pyc`, zips internos.
4. Gate reexecutado na maquina atual (baseline): pytest 116 passed, ruff limpo, doctor ok apos correcao do ponteiro `runs/latest_run.txt` (era caminho absoluto Windows; agora relativo portavel apontando para a run real `experiment_i_boundary_scan_20260812T145800363579Z`).
5. Commit `0b00cc0` (import limpo pos-Auditoria V3).

Decisao recomendada para `runs/`:

- Versionar documentos resumidos, configs resolvidas, manifests, ranking e relatorios essenciais.
- Evitar versionar caches grandes, `__pycache__`, zips e duplicatas.
- Se o objetivo for reproducibilidade maxima para FEBRACE, manter as duas runs reais de 1 Myr, mas limpar duplicatas dentro de cada pasta.

### Prioridade 1 - paralelizacao segura

Status: CONCLUIDA em 2026-08-15 (Etapa 1 do PROMPT_EXECUCAO_PLANET9).

Implementar paralelismo por processo com escrita centralizada no processo pai.

Escopo recomendado do primeiro commit:

- adicionar utilitario de execucao paralela com `max_workers`;
- aplicar em `_run_candidates_and_finalize`;
- manter fallback sequencial;
- preservar ordem final dos outputs;
- nao alterar formulas fisicas;
- adicionar testes que comparem modo sequencial vs paralelo em budget pequeno.

Por que primeiro:

- reduz o gargalo real;
- torna viavel testar seeds, robustez e Monte Carlo maior;
- nao exige decisao cientifica nova.

### Prioridade 2 - consistencia numerica pequena

Padronizar `exact_finish_time=0` no caminho nao checkpointado.

Fazer em commit separado da paralelizacao para isolar qualquer diferenca numerica.

Status: CONCLUIDA em `2026-08-15` (Etapa 2). Delta documentado em 5.2 (`|delta energy_drift_rel| ~= 1.6e-07`).

### Prioridade 3 - benchmark real da maquina

Rodar `scripts/benchmark_integration_cost.py` na maquina real antes de qualquer promessa de tempo.

Nao usar o benchmark do sandbox para justificar artigo. Usar apenas como estimativa grosseira.

Status: PARCIALMENTE EXECUTADA em 2026-08-15 (Etapa 3). O arquivo anterior de `results/hardware_benchmark.json` (2026-08-12) NAO tinha proveniencia de hardware; o script agora grava `cpu_model`, `logical_cpus`, `physical_cores`, `hardware_platform`, `measured_on` e uma nota `provenance` dizendo que o numero vale somente para a maquina que o gerou.

O que foi medido ate agora:

- Ambiente atual (sandbox, NAO e o E3-1230 V2 do usuario): `Intel(R) Xeon(R) Processor @ 2.50GHz`, 2 nucleos/2 threads, `measured_on 2026-08-15T22:59:06Z`, 4 giants + 4 ETNOs + 1 P9 (10 particulas). Projecao ~14.6 h por par de controle em 4e9 yr, single-core, single-candidate.
- Este numero NAO e a referencia de prazo do artigo. A paralelizacao da Etapa 1 e o `exact_finish_time` da Etapa 2 ja estao fechados; o benchmark real precisa ser re-medido no E3-1230 V2 para servir de "depois da Etapa 1".

Pendente (requer maquina do usuario):

- Rodar `python scripts/benchmark_integration_cost.py` no E3-1230 V2 e commitar o JSON resultante como referencia real. Qualquer estimativa de tempo em artigo deve citar esse numero, nunca o do sandbox.

### Prioridade 4 - MEGNO opcional

Adicionar MEGNO como metrica opcional/experimental com seed fixa.

Nao promover para conclusao do artigo ate calibrar contra runs longas.

### Prioridade 5 - estatistica circular formal

Avaliar Rayleigh Z / Kuiper para dar p-valores e analise de poder.

Fazer depois que o pipeline estiver rapido e versionado.

Status: CONCLUIDA em 2026-08-15 (Etapa 5). Implementado como opcao
configuravel (`circular-stats`, read-only), NAO promovido a padrao.
Decisao Categoria B fechada: manter threshold ad hoc como default (ver
5.5) - Rayleigh/Kuiper com p=0.16-0.18 (n=13) nao e evidencia de ausencia
de clustering, e amostra insuficiente (poder exige ~39 ETNOs a rho=0.5,
80%). Documentado em LIMITACOES.md e no artigo (secao de limitacoes).

### Prioridade 6 - Tabela 4 / funil real (parameter_space_scan)

Status: CONCLUIDA em 2026-08-16. Scan real executado com
`max_stage3_samples` reduzido de 60 para 2 (decisao explicita do
usuario, Opcao 2, por restricao de tempo no sandbox de 2 nucleos).
Artefatos reais em `runs/montecarlo_20260816T001216569981Z/`
(`parameter_space_scan.csv`, `reduction_funnel_summary.json`). Resultado:
nos estagios avaliados (0-3), 100% dos pontos passam; percentuais antigos
do artigo (~45/28/15/8/3-5%) nao reproduzidos e removidos. Artigo (Tabela
5 + Secao 7) e LIMITACOES.md atualizados; poder estatistico da amostra
reduzida NAO recalculado (limitacao registrada, nao escondida).

### Horizonte 1.1 - angulos ω9/Ω9/M0 fixos vs. por linha

Status: DECIDIDO em 2026-08-16. Opcao 1 (manter fixos, 200/270/180 para
as 7 linhas). Ver `docs/CANDIDATOS_QUADRO2.md` para a justificativa
completa e a condicao de reabertura (apenas junto do Horizonte 2).

## 7. O que nao fazer agora

Nao fazer nesta fase:

- rodar `secular.yaml` ou qualquer integracao de horas/dias sem autorizacao explicita;
- reintroduzir no artigo alegacoes de 1-4 Gyr sem run real;
- misturar paralelizacao, WHFast corrector, MEGNO e Rayleigh no mesmo commit;
- commitar `__pycache__`, zips historicos ou artefatos duplicados;
- usar MEGNO como substituto de run secular;
- escolher sozinho thresholds cientificos novos;
- apagar historico de limitacoes em vez de marcar resolvido/pendente.

## 8. Plano de commits sugerido

Commit 1 - importar estado corrigido limpo:

- base: `workspace.zip`;
- incluir codigo, configs, docs, testes e artigo revisado;
- excluir caches/zips/artefatos redundantes;
- adicionar `.gitignore`;
- gate limpo.

Commit 2 - paralelismo seguro:

- workers retornam payloads;
- pai escreve cache/status/CSVs;
- `max_workers` configuravel;
- teste sequencial vs paralelo.

Status: concluido em `2026-08-15` (Etapa 1).

Commit 3 - consistencia `exact_finish_time`:

- padronizar caminho nao checkpointado;
- teste/regressao numerica pequena;
- registrar impacto esperado.

Status: concluido em `2026-08-15` (Etapa 2).

Commit 4 - benchmark real:

- executar benchmark na maquina real;
- atualizar `results/hardware_benchmark.json`;
- documentar que o resultado e da maquina local.

Status: PARCIAL em 2026-08-15 (Etapa 3). Script atualizado com proveniencia de hardware e rodado no sandbox (arquivo marcado como sandbox, nao referencia). Falta rodar no E3-1230 V2 do usuario e commitar o JSON real.

Commit 5 - MEGNO experimental:

- metrica opcional;
- seed fixa;
- docs deixando claro que e indicador auxiliar.

Status: concluido em `2026-08-15` (Etapa 4).

Commit 6 - estatistica circular (Rayleigh/Kuiper):

- opcao configuravel ao lado dos thresholds ad hoc;
- comparacao lado a lado sobre as runs reais;
- NAO promover a padrao nem reclassificar.

Status: concluido em `2026-08-15` (Etapa 5). Comparacao mostra que os 10 candidatos de interesse das runs reais nao seriam significativos por Rayleigh a alfa=0.05 (p 0.16-0.18) e que o catalogo (n=13) precisa de ~39 ETNOs para detectar rho=0.5 a 80% de potencia. Promocao a padrao permanece Categoria B, aguardando decisao (ver 5.5).

## 9. Resposta curta para retomar em novo chat

Este bloco e a UNICA coisa que uma sessao nova (sem historico de chat)
precisa ler para continuar de onde parou. Se este bloco divergir de
qualquer outra parte deste documento, ESTE bloco vence (e o outro deve
ser corrigido).

> **Estado em 2026-08-16.** Etapas 0-5 do PROMPT_EXECUCAO_PLANET9.md
> concluidas: import limpo (Etapa 0); paralelizacao segura com teste
> seq-vs-paralelo byte-identico (Etapa 1); `exact_finish_time=0`
> padronizado (Etapa 2); benchmark com proveniencia de hardware, mas
> ainda so do sandbox, nao do E3-1230 V2 real (Etapa 3, PARCIAL); MEGNO
> experimental isolado, nao usado como prova de estabilidade (Etapa 4);
> Rayleigh/Kuiper implementado como opcao configuravel, decisao Categoria
> B fechada de manter threshold ad hoc como default (Etapa 5). Tarefa 1
> (reconciliar LIMITACOES.md + artigo apos a Etapa 5) fechada em
> 2026-08-15. Scan real da Tabela 4 (Prioridade 6) executado e fechado em
> 2026-08-16 com `max_stage3_samples` reduzido de 60 para 2 (decisao
> explicita do usuario); artefatos reais em
> `runs/montecarlo_20260816T001216569981Z/`; percentuais antigos do
> artigo (~45/28/15/8/3-5%) nao reproduzidos e removidos; poder
> estatistico da amostra reduzida NAO recalculado (limitacao registrada).
> Horizonte 1.1 (ω9/Ω9/M0 fixos vs. por linha) decidido em 2026-08-16:
> Opcao 1, manter fixos (200/270/180) para as 7 linhas - ver
> `docs/CANDIDATOS_QUADRO2.md`.
>
> **Gate na ultima sessao com REBOUND disponivel:** 139 passed, ruff
> limpo, doctor ok. (Um chat novo sem REBOUND instalado nao consegue
> reexecutar isto - so ler os artefatos ja gerados.)
>
> **Sessao 2026-08-17 (Estabilizacao de gate pos-Etapa 1 - investigacao e fix de regressao real).** Re-executei o gate
> como baseline e encontrei 3 testes falhando que o gate anterior nao
> detectou: `test_circular_stats_report_over_real_run_read_only` e
> `test_observed_catalog_etnos_match_manifest` falhavam porque o manifesto
> de runs reais grava o `etno_catalog` como path absoluto Linux
> (`/workspace/data/etnos/catalog_validated.csv`) e o modulo
> `circular_report.py` nao fazia fallback quando o path absoluto nao
> resolvia; `test_candidate_failure_writes_crash_log` falhava porque o
> monkeypatch em `ReboundEngine.run_control_pair` nao se propagava para
> processos filhos do `ProcessPoolExecutor` da Etapa 1. Correcoes: (a)
> `circular_report.py` agora tenta o basename relativo a
> `run.parent.parent/data/etnos/` se o path absoluto do manifesto nao
> existir - leitura apenas, nao muda fisica nem classificacao; (b) o
> teste de crash_log agora seta `PLANET9_MAX_WORKERS=1` para forcar o
> caminho sequencial onde o monkeypatch funciona. Tambem ajustei
> `runs/latest_run.txt` do path Linux para o caminho Windows local
> (artefato ja existe em `runs/montecarlo_20260816T001216569981Z/`).
> Gate apos correcoes: 140 passed, ruff limpo, doctor ok (140 = 139
> anteriores + novo teste `test_candidate_failure_writes_crash_log_in_parallel_worker`).
>
> **Confirmacao explicita (sessao 2026-08-17):** crash_log confirmado
> funcional em modo paralelo via teste dedicado
> `test_candidate_failure_writes_crash_log_in_parallel_worker` (PASSED);
> a falha original do teste de monkeypatch era limitacao do pytest
> monkeypatch em processo separado do ProcessPoolExecutor (no Windows os
> workers sao spawned, nao forked, e o monkeypatch nao cruza a fronteira),
> nao bug de producao - o caminho de crash_log em paralelo ja funcionava
> corretamente; o teste antigo apenas nunca conseguia exercer esse
> caminho. O fix nao foi de producao, foi de teste: o teste
> `test_candidate_failure_writes_crash_log` passou a forcar
> `PLANET9_MAX_WORKERS=1` para validar a excecao capturada e logada no
> mesmo processo, e o novo teste `..._in_parallel_worker` usa o env var
> `PLANET9_FAIL_CANDIDATE` para disparar a falha dentro do worker real,
> atravessando o limite de processo sem depender de monkeypatch.
>
> **Runs reais existentes:** apenas 1 Myr - `experiment_angle_robustness`
> e `experiment_i_boundary_scan`. Nenhuma run secular (1e8 anos) ou de
> escala Gyr existe. Nao rodar secular sem autorizacao explicita e
> RECENTE (autorizacao de sessao anterior nao vale).
>
> **Pendencias abertas, sem decisao ainda (nesta ordem de bloqueio):**
> 1. Benchmark real no E3-1230 V2 do usuario (Prioridade 3) - precisa da
>    maquina dele; comando: `python scripts/benchmark_integration_cost.py`.
> 2. Estrategia final de versionamento de `runs/` (Horizonte 1.4).
> 3. Horizonte 2 - decisao de rodar run secular real (Categoria B, maior
>    custo - depende do benchmark real para estimar tempo). So faz
>    sentido depois de 1 resolvido.
> 4. Horizonte 3 (Estagios 4/5 do funil) e Horizonte 4 (ML/nulos) - nao
>    iniciar sem decisao explicita, dependem do Horizonte 2.
> 5. Horizonte 5 (fechamento para submissao) - ultimo passo, depende do
>    prazo real da FEBRACE (pergunta em aberto, nunca respondida no chat).
>
> **Proxima acao recomendada:** decidir a pendencia 1 (rodar benchmark
> real) ou a pendencia 2 (estrategia de `runs/`) antes de considerar o
> Horizonte 2 - ambas sao Categoria A/logistica, nao exigem decisao
> cientifica nova, e desbloqueiam a decisao maior.

