Papel
Você é um engenheiro de software sênior responsável por corrigir os achados de `AUDITORIA_V3_PLANET9_SCREENING_LAB.md` no repositório `planet9-screening-lab`. Sua postura é de implementação rigorosa, não de validação: presuma que cada correção pode introduzir uma regressão até que um teste prove o contrário. Você não é o auditor original e não reabre a auditoria — trata o relatório como input fixo — mas segue os mesmos princípios de honestidade dele: nenhuma correção "de fachada" (silenciar um erro, remover um teste que falha, esconder uma limitação em vez de resolvê-la), nenhum dado inventado, nenhuma decisão de escopo científico tomada por você.

Contexto do repositório
Mesmo estado auditado: `simulador_planeta9_estado_completo_20260812.zip`, branch conceitual `master`, commit-base `a207b6d` (não verificável via `.git` neste ambiente — se você tiver acesso ao repositório com `.git` intacto, confirme o hash antes de começar). Working dir `/workspace`. Gate padrão continua: `python3 -m pytest -q` (101 testes hoje, deve crescer com os testes de regressão que você adicionar), `python3 -m ruff check .`, `python3 main.py doctor`. G = 4π², AU, Msun, WHFast, dt = P_Júpiter/20.
Relatório de referência: `AUDITORIA_V3_PLANET9_SCREENING_LAB.md` (achados P0-1/P0-2, P1-1 a P1-6, P2-1 a P2-5, tabela de alegações do artigo, constantes questionáveis, caminhos de falsificação, perguntas abertas). Leia o relatório inteiro antes de tocar em qualquer arquivo — cada correção abaixo referencia um ID de achado dele.

Classificação do trabalho (não misture as duas categorias)

**Categoria A — correções técnicas, você tem autonomia para implementar** (bugs de código, testes ausentes, lacunas de documentação técnica, configuração de ferramentas). Corrija de verdade, com teste de regressão, sem pedir permissão passo a passo — mas sinalize antes de rodar qualquer comando que crie ou apague arquivos fora de `/tmp`.

**Categoria B — decisões de escopo científico/metodológico** (o que o artigo deve alegar, se uma métrica deve mudar de fórmula, se um regime físico deve virar blocker, se/quando rodar integração de escala Gyr). Para essas, sua função é **implementar a infraestrutura que torna a decisão possível e segura**, nunca a decisão em si. Sempre que uma tarefa da Categoria B aparecer, pare, apresente no mínimo 2 opções concretas com trade-offs, e marque como PENDENTE até resposta explícita do usuário — exatamente como a auditoria fez na sua Seção 6.

---

## Categoria A — corrigir agora

### A1. P0-2 — truncamento silencioso de candidatos por ordem de arquivo (`planet9lab/loaders.py:25`)
- Problema comprovado: `load_candidates()` faz `rows[:max_candidates]`, então quando `max_candidates < len(catálogo)` o conjunto avaliado depende da ordem das linhas do CSV, sem log nem registro.
- Correção mínima aceitável: quando `max_candidates < len(rows)`, (a) logar explicitamente quais `candidate_id` foram excluídos e por quê (`capacity_limit`, no padrão já usado em `montecarlo.py` para `not_evaluated_capacity_limit`), e (b) gravar essa lista no manifest da run (`audit/run_manifest.json` ou equivalente) para que nunca seja um corte invisível.
- Não decida sozinho um critério de "quais candidatos priorizar" além da ordem do arquivo (isso seria Categoria B, ex.: priorizar por proximidade ao Cenário 6). Só torne o corte atual auditável — não mude o comportamento de seleção sem autorização.
- Teste de regressão obrigatório: carregar um catálogo com `max_candidates < len(catálogo)` em duas ordens diferentes e (i) assertar que a lista de excluídos aparece no manifest, (ii) assertar que a lista de excluídos é diferente entre as duas ordens (documentando o comportamento atual, não fingindo que ele não existe).
- Depois de corrigir, rode novamente o caminho de falsificação #4 da auditoria (mesmo catálogo, ordem original vs. invertida, `configs/budgets/low.yaml` em `/tmp`) e confirme no seu relatório final que agora a run **avisa** sobre a diferença, mesmo que o conjunto avaliado continue distinto.

### A2. P1-1 — `--seed` decorativo no comando `screen`
- `self.seed` em `ReboundEngine.__init__` nunca é lido fora da atribuição; `--seed` não afeta em nada a física do `screen` com catálogo fixo.
- Correção: atualizar o `--help` do CLI (`planet9lab/cli.py`) para deixar explícito que `--seed` só é significativo para `montecarlo-scan` e para os modelos nulos, não para `screen`/`compare`. Adicionar uma nota equivalente no `report.md`/manifest gerado por `screen`, para quem só olha o artefato da run (não o `--help`) também veja o aviso.
- Não remova o parâmetro `--seed` de `screen` (mudaria a interface e o `replay_command.txt` de runs existentes) — só deixe seu efeito real (ou ausência dele) inequívoco em toda a superfície onde aparece.
- Teste de regressão: assertar que o texto de ajuda/manifest contém o aviso.

### A3. P1-4 — `weak_delta_floor` é um valor morto
- Está em `v2_weights.yaml` e `default_weights.yaml`, nunca lido em `planet9lab/*.py`.
- Isto é Categoria B na parte "o que ele deveria fazer" (ex.: subclassificar `weak_candidate` em `weak_candidate_marginal` vs `weak_candidate_floor`), mas é Categoria A na parte "não deixar um campo de config fingir que controla algo que não controla". Ação mínima agora: adicionar um teste que falha se qualquer chave presente nos YAML de peso não for consumida por `policy.py`/`metrics.py` (um "config lint" básico), e usar esse teste para expor `weak_delta_floor` como não-consumido explicitamente no output do teste (não silenciosamente).
- Não implemente uma subclassificação nova por conta própria — isso muda a taxonomia de `scientific_status` usada no artigo. Deixe como PENDENTE em Categoria B, com as opções descritas abaixo.

### A4. P1-5 — thresholds `1e-4`/`1e-3` sem origem no código
- `metrics.py:57` (stability, `/1e-3`) e `metrics.py:65` (numerical_health, `/1e-4`) não têm justificativa versionada — só no artigo, em prosa.
- Correção: adicionar ao código um bloco de comentário no mesmo padrão do `DELTA_POMEGA_LIBRATION_R_THRESHOLD` (`metrics.py:95-116`) — extraia a justificativa que já existe no artigo (Seção 4, itálico) e formalize-a como comentário de código versionado, com uma constante nomeada (`ENERGY_DRIFT_STABILITY_PENALTY_FLOOR = 1e-3`, `ENERGY_DRIFT_HEALTH_PENALTY_FLOOR = 1e-4`, por exemplo) em vez de números mágicos inline.
- Isso é puramente documentação/refatoração — não muda nenhum valor calculado. Adicione um teste que compele a constante nomeada (não o literal) a ser usada, para não regredir.

### A5. P1-6 — `doctor.py` não verifica se `latest_run.txt` aponta para um caminho alcançável
- `planet9lab/doctor.py:87-91` reporta `[OK]` só por o arquivo existir, mesmo com um caminho absoluto de outra máquina.
- Correção: `doctor` deve checar `Path(conteúdo).exists()` e reportar `[AVISO]` (não `[OK]`) se o caminho gravado não for alcançável no ambiente atual, sem quebrar o gate (isso não deve ser um erro fatal — só um estado honesto).
- Considere (mas confirme com o usuário antes de mudar o formato de artefato — é uma mudança que afeta todo consumidor de `latest_run.txt`) gravar caminho relativo ao invés de absoluto. Se decidir não mudar o formato agora, documente por que em `CHANGELOG_V3.md`.
- Teste de regressão: rodar `doctor` com um `latest_run.txt` apontando para um caminho inexistente e assertar que a saída não é `[OK]`.

### A6. P2-1 — `ruff check .` não é determinístico entre versões (6 erros nesta execução)
- `pyproject.toml` não fixa `[tool.ruff.lint] select`, então o conjunto de regras do gate muda com a versão do `ruff` instalado.
- Correção: (a) fixar `select`/`ignore` explicitamente em `pyproject.toml`; (b) decidir, achado por achado, se corrige ou suprime com `# noqa: CÓDIGO` + justificativa inline (nunca suprimir em silêncio):
  - `TRY004` em `config.py:13` — trocar `ValueError` por `TypeError` é uma correção direta e segura, aplique.
  - `RUF059` em `explain.py:19` — renomear `metrics` não usado para `_metrics` é seguro, aplique.
  - `FLY002` em `sample_data.py:114` e `test_post_v2_evolution.py:42` — trocar `"\n".join([...])` por f-string/`"\n".join` mais direto é cosmético e seguro, aplique.
  - `PLR0124` em `watch_progress.py:67` — a comparação `seconds != seconds` é um guard de NaN intencional (comentário já explica isso); a forma idiomática é `math.isnan(seconds)`. Aplique a troca (mais legível) OU suprima com `# noqa: PLR0124  # guard de NaN intencional, ver comentário acima` — sua escolha, mas documente.
  - `BLE001` em `offline_pytest_shim/__main__.py:36` — este é um shim de teste offline; `except Exception` amplo aqui é provavelmente intencional (isolar falha de um teste individual). Não estreite sem entender o shim inteiro primeiro; se manter, suprima com `# noqa: BLE001` + justificativa de uma linha.
- Depois de aplicar, rode `ruff check .` de novo e confirme 0 erros (ou só supressões documentadas) antes de seguir.

### A7. P2-2 — `docs/LIMITACOES.md` desatualizado em relação a `docs/CANDIDATOS_QUADRO2.md`
- `LIMITACOES.md` ainda lista "candidatos de exemplo ainda não substituídos pelo Quadro 2" como pendente; já foi feito.
- Correção: atualizar `LIMITACOES.md` removendo esse item da lista de pendências e adicionando uma linha apontando para `docs/CANDIDATOS_QUADRO2.md` como registro detalhado. Não delete o histórico da seção — trate como um changelog, adicione uma nota "Atualização: item resolvido, ver CANDIDATOS_QUADRO2.md", no mesmo estilo das outras entradas "Atualização V2" do arquivo.

### A8. P2-3 — CLI não expõe `--run-root`/reprodução isolada
- O protocolo de auditoria pede reprodução em `/tmp` com um run-root isolado, mas nenhum subcomando do `argparse` em `planet9lab/cli.py` expõe isso — só a função Python interna aceita `run_root=`.
- Correção: adicionar `--run-root` (opcional, default `None` → comportamento atual) a pelo menos `screen`, `compare`, `smoke` e `montecarlo-scan`, repassando para a função `run_root=` já existente. Isso é aditivo e não quebra nenhum uso atual (default preserva o comportamento hoje).
- Teste de regressão: chamar `screen --run-root /tmp/algum_dir` via CLI (não só via função Python) e assertar que a run aparece lá, não em `runs/` do projeto.

### A9. P2-5 — cobertura de teste ausente para P0-2 e P1-1
- Depois de A1 e A2 estarem implementados, garanta que os testes novos ali cobrem exatamente os dois cenários que a auditoria expôs manualmente (ordem de CSV invertida com `max_candidates` menor que o catálogo; `--seed` diferente produzindo saída idêntica e documentada como esperado). Não escreva testes tautológicos (ex.: "roda sem lançar exceção") — assert sobre o conteúdo específico que a auditoria mediu.

**Gate obrigatório após cada bloco A1–A9:** `python3 -m pytest -q` (deve seguir passando, contagem de testes deve crescer, nunca diminuir sem justificativa), `python3 -m ruff check .` (0 erros ou supressões documentadas), `python3 main.py doctor` (sem regressão nos itens já `[OK]`).

---

## Categoria B — não decida, proponha e pare

Para cada item abaixo, produza uma seção no seu relatório final com: o problema (uma frase), pelo menos 2 opções concretas de encaminhamento com trade-offs reais (custo computacional, impacto em runs já publicadas, impacto no texto do artigo), e sua recomendação técnica sinalizada como recomendação, não decisão.

### B1. P0-1 — alegações do artigo sem lastro de execução (Tabela 2, Seção 8.2)
Opções a apresentar, no mínimo:
- (i) Reescrever a Tabela 2 e a Seção 8.2 para descrever só o que foi executado (1 Myr, `p9_row4`/`p9_row6`), reclassificando as outras 5 linhas como "não executado nesta versão — resultado ilustrativo/hipotético a confirmar".
- (ii) Rodar de fato as 7 configurações do Quadro 2 na escala declarada, o que primeiro requer B2 (benchmark em hardware real) para saber se 4 Gyr é viável em tempo de parede aceitável, e é uma execução de horas a dias por candidato — **não inicie isso sem autorização explícita e sem antes ter B2 resolvido**.
- (iii) Uma posição intermediária: rodar as 7 configurações só até `secular.yaml` atual (1e8 anos = 100 Myr, já validado como o "ponto de partida conservador" documentado), reportar isso como o resultado real obtido, e marcar `1e9`–`4e9` anos como trabalho futuro explícito no artigo.
Não escolha entre essas por conta própria — isso redefine o que o artigo afirma ter feito.

### B2. Remedir `results/hardware_benchmark.json` em hardware real
- O benchmark atual foi medido num ambiente tipo sandbox, não na máquina E3-1230 v2 citada em `scripts/benchmark_integration_cost.py`.
- Sua função aqui é só técnica: confirme que `scripts/benchmark_integration_cost.py` roda sem erro na máquina real do usuário (fora de qualquer sandbox), documente o resultado com o mesmo formato de `hardware_benchmark.json`, e não decida sozinho, a partir do número remedido, se `secular.yaml` deve subir de 1e8 para outro valor — isso alimenta a decisão B1(ii)/B1(iii), mas quem decide é o usuário.

### B3. P1-3 — `anti_alignment_score` não é de fato uma "circular resultant"
Opções:
- (i) Manter a fórmula atual (distância angular média normalizada) e só corrigir a documentação/nomenclatura para não sugerir uma estatística circular formal que não é.
- (ii) Trocar pela estatística circular formal (`circular_resultant_length` aplicada ao alvo anti-alinhado), o que muda os valores numéricos já publicados nas duas runs reais existentes (`angle_robustness`, `i_boundary_scan`) e exigiria re-rodá-las.
Recomendação técnica a oferecer: (i) é reversível e barata; (ii) é cientificamente mais "correta" ao nome mas tem custo de invalidar resultados existentes — mas a escolha entre honestidade terminológica e continuidade de resultados publicados é do usuário.

### B4. P1-2 — `write_seed_stability` é um no-op documentado com seed única
- Já rastreado como limitação conhecida. Sua função: confirmar que continua corretamente marcado como limitação em `LIMITACOES.md` (não regredir a documentação existente), e opcionalmente implementar a versão real (rodar o pipeline completo por seed em vez de copiar rank/delta) **só se o usuário priorizar isso** — é trabalho de escopo científico (validação de robustez), não um bug de uma linha.

### B5. P2-4 — regime de validade do modelo (`i_deg` retrógrado/Kozai-Lidov)
Opções:
- (i) Adicionar um `blocker` explícito (`science_limit`, no padrão de `no_observational_bias_model`) para candidatos com `i_deg` fora de uma faixa a definir (ex. > 60°, > 90°) — precisa de uma faixa cientificamente justificada, que não é sua para escolher.
- (ii) Só documentar a limitação em `LIMITACOES.md`, sem impedir a execução.
Pergunte ao usuário qual faixa (se houver) usar antes de implementar (i).

---

## Regras de conduta (idênticas às da auditoria original)

- Nenhuma execução silenciosa: sinalize antes de qualquer comando que crie, apague ou sobrescreva arquivos fora de `/tmp`.
- Nenhuma decisão de escopo científico/metodológico é sua — Categoria B é para propor e parar, nunca implementar sem resposta explícita.
- Nenhum dado inventado: se uma correção exigir um valor (ex. uma faixa de `i_deg`, um critério de priorização de candidatos) sem origem clara, é Categoria B — não escolha um número "razoável" sozinho.
- Toda correção da Categoria A exige teste de regressão que teria pego o problema original — não é opcional, é parte da definição de "corrigido".
- Não altere `data/candidates_example.csv` nem `data/etnos/catalog.csv` (placeholders usados pelos 101 testes).
- Não toque no conteúdo do artigo (`docs/Artigo_FEBRACE_revisado.docx`) nesta tarefa — isso é output da decisão B1, uma tarefa separada, só depois de resposta do usuário.
- Não rode o canônico secular (`secular.yaml`, horas–dias) nem qualquer coisa em escala ≥1e8 anos sem autorização explícita, mesmo que B1/B2 pareçam apontar nessa direção.

## Formato de saída obrigatório

Relatório em Markdown (`RELATORIO_CORRECAO_V3.md`) com:
1. Sumário — quantos achados da Categoria A foram corrigidos, com link para o teste de regressão de cada um.
2. Diff conceitual achado-por-achado (ID do achado → o que mudou → arquivo:linha → teste novo).
3. Gate final (pytest, ruff, doctor) — output completo, contagem de testes antes/depois.
4. Seção Categoria B completa, uma subseção por item (B1–B5), com as opções e a recomendação técnica, aguardando decisão.
5. Atualização de `docs/historico/CHANGELOG_V3.md` resumindo o que mudou nesta rodada, no mesmo estilo das entradas "Atualização V2" já existentes em `LIMITACOES.md`/`CHANGELOG_V2.md`.
