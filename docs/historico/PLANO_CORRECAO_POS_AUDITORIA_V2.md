# Plano de Correção Pós-Auditoria V2 (simulador_v2_doctor_fix)

> Documento de trabalho — não reflete o estado atual do código. A auditoria de
> referência é a sessão `simulador_v2_doctor_fix` (89/89 testes, `doctor` OK,
> REBOUND real, 34 avisos `ruff`). Nenhuma correção foi aplicada até a aprovação
> deste plano.

## 0. Mandato do executor

O executor deve aplicar **apenas** os itens P0-P3 abaixo, exatamente como
especificados, e nada mais. Cada item tem âncora de arquivo:linha, mudança
cirúrgica e verificação própria. O critério de aceite global é: **comportamento
observável idêntico ao de hoje** para todo fluxo não listado nos itens, com a
suíte verde e `runs/` do projeto limpa após os testes.

### Guarda-corpos (regras de ouro — violar qualquer uma é reprovação)

1. **Proibido reescrever módulos do zero.** Toda mudança é edição pontual nos
   trechos com âncora explícita.
2. **Proibido adicionar funcionalidade.** Nada de `--all` no `watch_progress`,
   nem novo subcomando, nem novo budget/config, nem novo filtro científico.
3. **Proibido mudar parâmetros científicos.** `configs/`, `data/`, `secular.yaml`
   (Achado 7 fechado), thresholds, pesos e strings de artefatos não são tocados.
4. **Proibido renomear API pública existente.** Assinaturas de `run_screen`,
   `run_smoke`, `run_compare`, `execute_run`, `resume_run`, `write_root_copies`
   e funções de teste continuam válidas; só é permitido **adicionar parâmetro
   opcional com default**.
5. **Proibido apagar arquivos** (regra do projeto). Arquivo morto vai para
   `scripts/archived/` com nota, nunca para `rm`.
6. **`print()` de saída ao usuário permanece intacto.** Observabilidade é
   somada via `logging` padrão; não substitui a saída existente.
7. **Nenhuma dependência nova.** Só biblioteca padrão + o que já existe no
   `pyproject.toml`.
8. **Sem `# noqa` genérico e sem desligar regras no `ruff`.** Os avisos restantes
   após o item P2 devem ser exatamente os já justificados no código.
9. **Cada item termina com sua verificação rodada e passando** antes de passar
   ao próximo; o gate final (item 6) roda por último.

---

## DECISION GATE (obrigatório) — Achado 2: destino do `paramscan.py`

Confirmado pela auditoria e pelo `CHANGELOG_V2.md` (linhas 80-86): `paramscan.py`
nunca foi importado por nenhum módulo, não é exposto na CLI e não tem teste.
`montecarlo.py` é a implementação de fato do item 2 do plano (wireada em
`montecarlo-scan`), cobre o mesmo funil com 4 estágios computados e é a citada
em `docs/LIMITACOES.md`. O executor **deve obter decisão do usuário** antes de
tocar em `paramscan.py`; os itens P0/P1/P2 não dependem dessa decisão e podem
começar enquanto ela não chega.

### Opção A (recomendada) — arquivar fora do pacote

Motivo: unificar/duplicar o funil em dois módulos simultâneos criaria dois
artefatos científicos paralelos (risco de achar que `paramscan-scan` é o
resultado oficial quando não é). `montecarlo.py` é estritamente mais completo.

Passos:
- Mover `planet9lab/paramscan.py` para `scripts/archived/paramscan.py`.
- Adicionar cabeçalho no topo do arquivo movido: nota de descontinuação
  apontando para `planet9lab/montecarlo.py` como sucessor wireado, e data.
- Fechar a nota "decisão futura pendente" em `docs/historico/CHANGELOG_V2.md`
  (linhas 80-86): registrar que a decisão foi tomada (arquivar), com data.
- `docs/LIMITACOES.md`: nenhuma alteração de conteúdo (já cita `montecarlo.py`).
- Verificação: `python -m pytest` verde; `python main.py montecarlo-scan
  --config configs/montecarlo/parameter_space.yaml` continua expondo o funil
  oficial; `grep -rn "paramscan" --include="*.py" planet9lab/` sem resultados.

### Opção B — wirear à CLI e testar

Só justificável se o artigo da FEBRACE citar nominalmente `paramscan.py` e seu
formato de saída (colunas `pass_*` e `survives_all_implemented_filters`).
Passos:
- Criar `run_paramscan(...)` em `run.py` (mesma disciplina de proveniência de
  `run_montecarlo_scan`: `run_id`, hashes, `environment.json`,
  `replay_command.txt`, `SUCCESS/FAILED.marker`, `latest_run.txt`).
- Subcomando `paramscan-scan` na CLI com `--config` e `--seed`.
- Testes novos cobrindo `run_reduction_funnel` com pontos sintéticos e o
  subcomando.
- **Risco registrado**: duplicação conceitual com `montecarlo.py`; mitigar com
  docstring cruzada nos dois módulos apontando a relação.

---

## P0 (CRÍTICA) — Achado 1: testes isolados de `runs/` real

Problema: `run.py` usa `ROOT / "runs"` em 4 pontos (linhas 319, 603, 825, 872);
`run_screen` chamado pelos testes cria pastas reais em `runs/` e sobrescreve
`runs/latest_run.txt` (31 pastas / 5.8 MB na auditoria), podendo ser confundidas
com run científica.

**Âncora:** `planet9lab/run.py:37, 319, 603, 825, 872`.

Mudança em `planet9lab/run.py` (edição pontual, sem mudar `default_paths()` —
dados/configs continuam resolvidos por `ROOT`, que NÃO pode ser monkeypatchado):

1. Logo após `ROOT` (linha 37): `RUNS_DIR = ROOT / "runs"` e helper
   `def _runs_dir(run_root: Path | None) -> Path: return run_root if run_root is not None else RUNS_DIR`.
2. Substituir os 4 usos de `ROOT / "runs"` por `_runs_dir(...)`:
   - linha 319 (`execute_run`): `ensure_dir(_runs_dir(run_root) / run_id)`;
   - linha 603 (finalize): `write_text(_runs_dir(runs_dir_override) / "latest_run.txt", ...)`;
   - linha 825 e 872 (`run_montecarlo_scan`): idem com `run_root`.
3. Adicionar parâmetro opcional `run_root: Path | None = None` a `run_screen`,
   `run_smoke`, `run_compare`, `execute_run`, `run_montecarlo_scan` (passado ao
   ponto de criação da pasta). Adicionar parâmetro `runs_dir: Path | None = None`
   a `_run_candidates_and_finalize` (usado na linha 603). Default `None` =
   comportamento atual (backward compatible). `resume_run` não muda.
4. Novo `tests/conftest.py` com fixture **autouse** que aponta para `tmp_path`:

   ```python
   import pytest

   @pytest.fixture(autouse=True)
   def isolated_runs(tmp_path, monkeypatch):
       import planet9lab.run as run_module
       monkeypatch.setattr(run_module, "RUNS_DIR", tmp_path)
       return tmp_path
   ```

   Assim os ~35 call sites existentes de `run_screen(...)` ficam isolados **sem
   editar nenhum teste existente**. Como `default_paths()` continua usando `ROOT`,
   os catálogos/configs reais seguem sendo lidos — apenas o destino da run muda.

5. Testes novos em `tests/test_run_artifacts.py`:
   - `test_runs_are_isolated_from_project_runs_dir` — `run_screen(...)` retorna
     caminho sob `tmp_path`; `planet9lab.run.RUNS_DIR / "latest_run.txt"` existe;
     o `runs/` real do projeto continua contendo apenas `README.md`.
   - `test_latest_run_pointer_written_to_isolated_dir` — após `run_screen`, o
     pointer existe dentro de `tmp_path` e aponta para uma pasta existente.

**Verificação:** `python -m pytest` → 89 + novos testes, e `ls runs/` mostra
apenas `README.md`; `runs/latest_run.txt` não existe na raiz do projeto.

---

## P1 — Achado 4: `sync_root_copy()` + teste de paridade

Problema: `write_root_copies` (`run.py:743-756`) duplica 9 artefatos na raiz da
run, mas `robustness.py` reimplementa a duplicação à mão em 4 pontos
(`merge_blocker` linha 342; `refresh_v2_report` linhas 354, 358, 359-362).

**Âncora:** `planet9lab/run.py:716-756`, `planet9lab/robustness.py:335-364`.

Mudanças:
1. Em `planet9lab/run.py`, junto de `write_root_copies`:
   - `def sync_root_copy(run_dir: Path, source: str, target: str) -> None:` que
     faz `shutil.copyfile(run_dir / source, run_dir / target)` (1 linha).
   - Refatorar `write_root_copies` para iterar o `copy_map` existente chamando
     `sync_root_copy` (o mapa de 9 pares não muda de conteúdo).
2. Em `planet9lab/robustness.py`:
   - `merge_blocker` (linha 342): substituir `write_json(run_dir / "blockers.json",
     data)` por `sync_root_copy(run_dir, "audit/blockers.json", "blockers.json")`
     (importar `sync_root_copy` de `.run`).
   - `refresh_v2_report`: escrever apenas no local canônico
     (`results/ranking.csv`, `reports/report.md`,
     `presentation/summary_for_presentation.md`) e chamar
     `write_root_copies(run_dir)` ao final — removendo as 4 escritas manuais de
     raiz. A ordem de escrita (canônico antes da cópia) garante paridade de bytes.
3. Teste de propriedade em `tests/test_run_artifacts.py`
   (`test_root_copies_match_canonical_locations`): após `run_screen`, para cada
   um dos 9 pares `(canônico, raiz)` do `copy_map`, comparar `read_bytes()` — deve
   ser idêntico byte a byte.

**Verificação:** novo teste de paridade verde; `python -m pytest` verde; depois
de `leave_one_out` + `null_models` + `refresh_v2_report` (teste V2 existente),
o ranking/report/blochers da raiz continuam idênticos aos canônicos.

---

## P1 — Achado 5 + 6: observabilidade (`logging`) e log de crash por candidato

Problema: zero `import logging` no pacote; 49 `print()` sem timestamp; os 5
`except Exception` guardam `type(exc).__name__` (engine.py:182, 268, 360) ou
`str(exc)` sem traceback (run.py:495, 864), dificultando debug pós-morte de run
longa. A saída ao usuário (`print()`) **não muda**.

**Âncora:** `planet9lab/cli.py:107-110`, `planet9lab/run.py:462-512, 857-872`,
`planet9lab/engine.py:182-184, 267-268, 360-362`.

Mudanças:
1. `planet9lab/cli.py`: no topo de `main()` (antes do `try`), configurar uma vez:
   ```python
   logging.basicConfig(level=logging.INFO,
                       format="%(asctime)s %(levelname)s %(name)s: %(message)s")
   ```
   (stdlib; `basicConfig` é no-op se já configurado). `import logging` no topo.
   `doctor.py` permanece intocado (não pode importar nada).
2. `planet9lab/run.py`: `logger = logging.getLogger("planet9lab.run")`. No
   handler `except Exception as exc` do laço de candidatos (linha 495): além do
   fluxo atual (que já grava `error=str(exc)` no `events.log` via
   `append_event`), emitir `logger.error("candidate failed: %s", candidate.candidate_id, exc_info=True)`
   e chamar novo helper `append_crash(run_dir, candidate.candidate_id, "control_pair", exc)`
   que grava `audit/crash_log.jsonl` com `timestamp`, `candidate_id`, `branch`,
   `exception_type`, `error` e `traceback` (via `traceback.format_exc()`), 1 JSON
   por linha. No `except` do `run_montecarlo_scan` (linha 864): `logger.error(..., exc_info=True)`.
3. `planet9lab/engine.py`: `logger = logging.getLogger("planet9lab.engine")`.
   Nos 3 pontos (182, 268, 360), preservar a string de `failures` (contrato de
   métricas existente) e somar `logger.warning("...: %s", type(exc).__name__, exc_info=True)`
   — o traceback vai para stderr apenas, sem alterar artefatos da run.
4. Não criar módulo novo; sem tocar nos demais `print()`.

**Verificação:** rodar `python main.py screen --budget configs/budgets/low.yaml
--seed 12345` e confirmar linhas timestamped no stderr; forçar um candidato
falho via teste (budget apontando para caminho inexistente de candidato) e
confirmar `audit/crash_log.jsonl` com `traceback` não vazio; `python -m pytest`
verde.

---

## P2 — Achado 8: lint `ruff` (auto-fix seguro)

Problema: 34 avisos; 24 corrigíveis automaticamente sem mudança de comportamento
(imports não usados, ordem de imports, `datetime`, imports deprecados, f-string).

**Âncora:** repositório inteiro; `pyproject.toml:27-29` (`[tool.ruff]`) intocado.

Mudanças:
1. `ruff check . --fix` (roda os auto-fixes).
2. Revisar o diff: não deve tocar em nenhum arquivo fora do esperado
   (módulos do pacote + testes + scripts).
3. `ruff check .` de novo: os ~10 avisos restantes devem ser exatamente os
   justificados (BLE001 com `# noqa` em `doctor.py`; idiom `seconds != seconds`
   em `scripts/watch_progress.py:67`; etc.). **Não** adicionar `# noqa`, não
   desligar regra, não mexer no `pyproject.toml`.

**Verificação:** `ruff check .` com contagem ≤ 10 e todos justificáveis;
`python -m pytest` verde; `python main.py doctor` OK.

---

## P2 — Reproducibilidade: hash do commit git no manifest

Problema (nota da auditoria, reprodutibilidade 8): `audit/run_manifest.json` e
`environment.json` não registram o commit git da run.

**Âncora:** `planet9lab/run.py:129-136` (`environment_info`), `561-580` (manifest).

Mudanças:
1. Novo helper em `run.py`:
   ```python
   def git_commit() -> str:
       try:
           proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True, check=True, timeout=5)
           return proc.stdout.strip() or "unknown"
       except (OSError, subprocess.SubprocessError):
           return "not-a-git-repo"
   ```
2. `environment_info()` ganha `"git_commit": git_commit()`.
3. O dict `manifest` (linha 561) ganha `"git_commit": git_commit()`.
4. Nenhum outro campo do manifest muda; auditoria (`audit.py`) não exige o campo,
   então nenhum teste existente quebra.

**Verificação:** rodar `screen` curto e conferir `audit/run_manifest.json` e
`environment.json` com `git_commit` preenchido; `python -m pytest` verde.

---

## P3 — Achado 3: artefato de texto na docstring

Problema: `paramscan.py:15` — `"seeAssistant NOT_IMPLEMENTED_FILTERS"` (palavra
"Assistant" colada por artefato de edição).

**Âncora:** `planet9lab/paramscan.py:15` (se o DECISION GATE escolher a Opção A,
a edição acontece no arquivo já movido para `scripts/archived/paramscan.py`).

Mudança: `"seeAssistant NOT_IMPLEMENTED_FILTERS"` → `"see NOT_IMPLEMENTED_FILTERS"`.
Única ocorrência no repositório (confirmado por grep na auditoria).

**Verificação:** `grep -rn "seeAssistant" .` → sem resultados; `ruff`/pytest sem
novas falhas.

---

## Achado 7 e Achado 9 — sem ação

- **Achado 7 (`secular.yaml`)**: fechado pela auditoria; nenhuma mudança.
- **Achado 9 (`watch_progress --all`)**: registro de funcionalidade futura,
  explicitamente **fora** do escopo ("não adicionar funcionalidades").

---

## 5. Registro no histórico do projeto

Após todas as correções aplicadas e verificadas, **apenas**:
- Adicionar seção em `docs/historico/CHANGELOG_V2.md` intitulada
  "Correções pós-auditoria (simulador_v2_doctor_fix)" listando, em bullet curto,
  cada item aplicado e o resultado da verificação. Nada além disso.
- Se a Opção A foi escolhida, fechar a nota de "decisão futura pendente" do
  `paramscan.py` conforme especificado no DECISION GATE.

`docs/LIMITACOES.md` e `README.md` **não** mudam (nenhuma limitação foi
removida nem adicionada por estes itens).

## 6. Gate final de aceite (rodar nesta ordem)

1. `python -m pytest` → 89 + novos testes, todos verdes.
2. `ls runs/` → apenas `README.md`; `runs/latest_run.txt` ausente na raiz.
3. `python main.py doctor` → tudo OK.
4. `ruff check .` → apenas os avisos justificados restantes (≤ ~10).
5. `python main.py screen --budget configs/budgets/low.yaml --seed 12345` →
   run real criada em `runs/`, `git_commit` presente no manifest.
6. `python main.py audit-run <run_id>` → `AUDIT OK`.
7. `git status` → apenas os arquivos previstos neste plano (nenhum arquivo
   inesperado, nenhum `configs/` ou `data/` tocado).

Critério de parada: se qualquer verificação de item falhar, corrigir dentro do
escopo do item (sem desviar para "reforço") ou reportar e parar. Nenhuma correção
fora dos itens P0-P3 pode ser aplicada mesmo que pareça tentadora.
