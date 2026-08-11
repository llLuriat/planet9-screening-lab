# runs/

Esta pasta começa vazia de propósito. Cada execução de `screen`,
`compare`, `smoke` ou `montecarlo-scan` cria uma subpasta nova aqui
(`<comando>_<timestamp>Z/`) com todos os artefatos daquela run.

`latest_run.txt` aponta para a run mais recente e é usado por padrão
pelos comandos `status`/`watch`.

Runs antigas de teste/desenvolvimento podem ser apagadas manualmente
a qualquer momento - nada além de `latest_run.txt` referencia runs
específicas, e ele é regenerado a cada run nova.
