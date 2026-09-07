# Setup do zero — planet9-screening-lab

Guia único, em ordem, do PC vazio até rodar o pipeline e commitar. PowerShell
(Windows). Roda de cima pra baixo — cada bloco assume que o anterior já
funcionou.

Se algum comando der erro, **não pula pro próximo** — resolve o erro daquele
bloco primeiro (a seção "Problemas comuns" no final cobre os que já
apareceram).

---

## 0. Pré-requisitos (só na primeira vez nessa máquina)

```powershell
python --version
git --version
```

- Se `python` não for reconhecido: instala em https://www.python.org/downloads/
  marcando **"Add python.exe to PATH"** na tela de instalação. Precisa 3.11+.
- Se `git` não for reconhecido: instala em https://git-scm.com/download/win.
  Depois de instalar, **fecha e abre o terminal de novo** — o PATH só atualiza
  em sessões novas. Se mesmo assim continuar não reconhecendo, veja
  "Problemas comuns" no final.

Configura sua identidade no Git (só precisa uma vez por máquina):
```powershell
git config --global user.name "Seu Nome"
git config --global user.email "seu-email@dominio.com"
```

---

## 1. Clonar o repositório

```powershell
cd C:\Users\SEU_USUARIO\Downloads
git clone https://github.com/lIIuriat/planet9-screening-lab.git
cd planet9-screening-lab
```

Confirma que está na pasta certa (deve ter `main.py`, `pyproject.toml`,
`planet9lab/` etc.):
```powershell
Get-ChildItem
```

---

## 2. Ambiente virtual

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

O prompt deve passar a mostrar `(.venv)` no início da linha. Se der erro de
"execução de scripts foi desabilitada":
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

---

## 3. Instalar dependências

```powershell
pip install -e .
```

Se o VS Code perguntar sobre criar/vincular ambiente virtual automaticamente,
pode aceitar — só confirma depois com o comando abaixo que a venv ativa é a
certa (dentro da pasta do projeto, não uma de fora):
```powershell
Get-Command python | Select-Object Source
```

---

## 4. Diagnóstico do ambiente — sempre rodar antes de qualquer outra coisa

```powershell
python main.py doctor
```

Todos os itens devem aparecer `[OK]`, principalmente
`rebound (simulação real)`. Se algo falhar, o próprio output diz o que
instalar — resolve antes de continuar.

---

## 5. Testes

```powershell
python -m pytest tests/ -q
```

Esperado: `96 passed`.

Confirma que os testes não sujaram a pasta `runs/` real do projeto:
```powershell
git status --porcelain runs/
```
Deve voltar **vazio**. Se voltar algo, pare e avise antes de continuar.

---

## 6. Lint (opcional, mas rápido)

```powershell
ruff check .
```

Esperado: 6 avisos, todos já conhecidos e justificados (não são bugs).

---

## 7. Benchmark de hardware — decide o orçamento de integração

```powershell
python scripts/benchmark_integration_cost.py
```

Escreve `results/hardware_benchmark.json` com uma recomendação de
`integration_years` honesta para essa máquina. Pode levar alguns minutos.

```powershell
Get-Content results\hardware_benchmark.json
```

Se o valor recomendado for diferente do que já está em
`configs/budgets/secular.yaml`, atualiza o YAML e o `docs/LIMITACOES.md` com
o número real medido nessa máquina antes de seguir — não force um valor que
não foi de fato testado aqui.

---

## 8. Rodar o pipeline

**Smoke test (rápido, minutos, só pra confirmar que o pipeline inteiro roda):**
```powershell
python main.py smoke
```

**Screen com um budget leve (minutos):**
```powershell
python main.py screen --budget configs/budgets/low.yaml --seed 12345
```

**Screen científico real com o budget secular (HORAS — confira o tempo
estimado no `hardware_benchmark.json` antes de rodar; pode levar dias):**
```powershell
python main.py screen --budget configs/budgets/secular.yaml --seed 12345
```

Acompanhar progresso em outro terminal (com a venv ativa também):
```powershell
python main.py watch
```

Antes de disparar uma run longa: desativa a suspensão automática do Windows
(Configurações > Sistema > Energia), senão a run morre no meio se a máquina
dormir.

---

## 9. Auditar e conferir a run

```powershell
python main.py status
python main.py audit-run (Get-Content runs\latest_run.txt)
```

Esperado: `AUDIT OK`.

---

## 10. Commit e push

```powershell
git status --porcelain runs/    # confere o que vai entrar (deve seguir vazio, salvo se você decidiu manter algo de propósito)
git add -A
git status                      # confere antes de commitar
git commit -m "descrição do que mudou"
git push
```

(depois do primeiro `git push -u origin main`, um `git push` simples já basta
nas próximas vezes)

---

## Problemas comuns

**`git`/`python` "não é reconhecido como nome de cmdlet"**
Instalado mas fora do PATH da sessão atual. Acha onde está instalado:
```powershell
Get-ChildItem -Path "C:\Program Files\Git","C:\Program Files (x86)\Git" -Recurse -Filter "git.exe" -ErrorAction SilentlyContinue
```
Adiciona no PATH permanente do usuário (uma vez só):
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files\Git\cmd", "User")
```
Fecha e abre o terminal de novo depois disso.

**`warning: ... LF will be replaced by CRLF ...` no `git add`/`git status`**
Normal no Windows, não é erro. Ignora.

**`fatal: not a git repository`**
Você não está dentro da pasta do projeto, ou o `git init`/`git clone` não
rodou ainda ali. Confere com `Get-Location` e `Get-ChildItem`.

**`fatal: remote origin already exists`**
Já tem um remote cadastrado (de uma tentativa anterior). Vê qual é:
```powershell
git remote -v
```
Se estiver errado:
```powershell
git remote remove origin
git remote add origin https://github.com/lIIuriat/planet9-screening-lab.git
```

**`.venv` aparecendo no `git status`/`git add`**
O `.gitignore` do projeto já cobre `.venv/`, `venv/`, `env/`, `__pycache__/`.
Se mesmo assim aparecer, confirma se está rodando os comandos de dentro da
pasta certa do projeto (onde está o `.gitignore`), não de uma pasta acima.

**`pytest` criou pastas dentro de `runs/` do projeto real**
Não deveria acontecer (isso foi corrigido e há um teste que garante isso —
`test_runs_are_isolated_from_project_runs_dir`). Se acontecer, é regressão:
pare, não commite essas pastas, e revise `tests/conftest.py` e a fixture
`isolated_runs` antes de continuar.
