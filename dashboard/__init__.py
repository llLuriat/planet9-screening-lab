"""Dashboard de controle e visualização de runs (Tarefa D).

Pacote 100% novo e separado do pipeline: NUNCA altera `cli.py` nem
qualquer módulo de `planet9lab/` — apenas lê os artefatos canônicos das
runs e dispara os subcomandos existentes via subprocess desacoplado.

Módulos:
- `config`: caminhos do estado local (`.dashboard/`) e defaults do servidor.
- `commands`: schema dos subcomandos disparáveis pelo formulário.
- `runstore`: leitura read-only de `runs/` (status, blockers, progresso).
- `report`: relatório HTML legível de uma run (caveats/interpretation
  verbatim — contrato travado por teste).
- `runner`: launcher de jobs detached (sobrevivem ao fechamento da UI).
- `app`: aplicação NiceGUI (bind exclusivo em 127.0.0.1).
"""

__version__ = "0.1.0"
