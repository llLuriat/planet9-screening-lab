"""Diagnóstico de ambiente. Roda com `python main.py doctor`.

IMPORTANTE: este módulo não pode importar nada de planet9lab.schemas,
planet9lab.engine ou planet9lab.run - todos esses dependem de pydantic (e
engine/run dependem, indiretamente, de rebound). Se qualquer uma dessas
dependências estiver faltando ou quebrada, `python main.py doctor` ainda
precisa rodar e dizer exatamente o que está errado, em vez de morrer com um
traceback antes de imprimir qualquer coisa útil. Por isso main.py trata
`doctor` como um caso especial, verificado ANTES de importar planet9lab.cli.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _check_importable(module_name: str) -> tuple[bool, str]:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        return False, "não encontrado"
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - diagnostic tool, wants to catch anything
        return False, f"encontrado mas falhou ao importar: {exc}"
    version = getattr(module, "__version__", None)
    return True, f"ok (versão {version})" if version else "ok"


def _check_no_shadowing_pytest_package() -> tuple[bool, str]:
    shadow = ROOT / "pytest"
    if shadow.exists():
        return False, (
            f"existe um pacote local em {shadow} que vai SOMBREAR qualquer pytest "
            "real instalado quando você rodar 'python -m pytest' desta pasta. "
            "Apague ou renomeie essa pasta."
        )
    return True, "nenhum pacote local 'pytest/' na raiz do projeto (bom)"


def _check_rebound_can_simulate() -> tuple[bool, str]:
    try:
        import rebound
    except Exception as exc:  # noqa: BLE001
        return False, f"não importável: {exc}"
    try:
        sim = rebound.Simulation()
        sim.add(m=1.0)
        sim.add(m=1e-3, a=1.0)
        sim.integrate(1.0)
    except Exception as exc:  # noqa: BLE001
        return False, f"importou mas falhou ao rodar uma integração mínima: {exc}"
    return True, "ok (integração mínima de teste funcionou)"


def run_doctor() -> int:
    print("=== planet9-screening-lab doctor ===\n")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Projeto: {ROOT}\n")

    all_ok = True
    checks: list[tuple[str, bool, str]] = []

    for module_name in ["yaml", "numpy", "pandas", "pydantic", "typer", "rich"]:
        ok, detail = _check_importable(module_name)
        checks.append((module_name, ok, detail))
        all_ok = all_ok and ok

    rebound_ok, rebound_detail = _check_rebound_can_simulate()
    checks.append(("rebound (simulação real)", rebound_ok, rebound_detail))
    all_ok = all_ok and rebound_ok

    pytest_ok, pytest_detail = _check_importable("pytest")
    checks.append(("pytest", pytest_ok, pytest_detail))
    all_ok = all_ok and pytest_ok

    shadow_ok, shadow_detail = _check_no_shadowing_pytest_package()
    checks.append(("pytest (sem sombra local)", shadow_ok, shadow_detail))
    all_ok = all_ok and shadow_ok

    latest_run = ROOT / "runs" / "latest_run.txt"
    if latest_run.exists():
        checks.append(("runs/latest_run.txt", True, latest_run.read_text(encoding="utf-8").strip()))
    else:
        checks.append(("runs/latest_run.txt", True, "não existe ainda (normal se você nunca rodou 'screen')"))

    width = max(len(name) for name, _, _ in checks)
    for name, ok, detail in checks:
        mark = "OK  " if ok else "FALHA"
        print(f"[{mark}] {name.ljust(width)}  {detail}")

    print()
    if not rebound_ok:
        print(
            "-> REBOUND não está funcional: 'screen'/'compare'/'smoke' vão recusar "
            "rodar como screening físico real (a menos que você force "
            "--allow-analytical-fallback, o que gera uma run marcada INVALID). "
            "Rode: pip install rebound"
        )
    if not pytest_ok:
        print("-> pytest não instalado. Rode: pip install pytest")
    if not shadow_ok:
        print("-> Veja a mensagem acima sobre o pacote 'pytest/' local.")
    if all_ok:
        print("Tudo certo. Pipeline pronto para uso real (REBOUND de verdade, sem fallback).")
    else:
        print("Resumo: há pendências acima. Depois de corrigi-las, rode 'python main.py doctor' de novo.")
    return 0 if all_ok else 1
