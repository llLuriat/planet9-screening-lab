"""Main file da simulação de usuário (nicegui.testing.User).

A simulação executa ESTE arquivo com ``runpy`` (``run_name='__main__'``)
e EXIGE ``ui.run()`` no nível do módulo. As rotas do dashboard são
registradas por decorator no corpo de ``dashboard/app.py`` — que já está
em ``sys.modules`` quando os testes importam ``dashboard.app`` — por isso
o corpo de app.py é REEXECUTADO aqui (``runpy.run_path``) para registrar
as rotas no app simulado recém-criado, antes de chamar ``main()``. Em
modo simulação o ``ui.run`` NÃO sobe servidor de verdade.
"""

import runpy
from pathlib import Path

_app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
_namespace = runpy.run_path(str(_app_path), run_name="dashboard_testing_app")
_namespace["main"]()
