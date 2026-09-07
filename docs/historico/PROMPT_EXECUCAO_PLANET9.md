# PROMPT DE EXECUÇÃO — Planet9 Screening Lab (pós-Auditoria V3)

> Cole este prompt inteiro, junto com o repositório atual, para o agente
> começar a **executar** — não é um documento de referência para consultar
> depois, é uma ordem de serviço. Ele já contém tudo que o agente precisa
> para trabalhar sozinho por várias sessões sem perder o fio: contexto,
> tarefa, restrições, ordem e formato de entrega.

---

<contexto>

Você está trabalhando no `planet9-screening-lab`, um pipeline REBOUND de
screening dinâmico para ETNOs (testa se um modelo com Planeta 9 melhora
métricas orbitais vs. controle sem P9 — **não** prova existência do P9, é
screening conservador).

Estado atual, verificado no código real (não em memória de chat):

- Auditoria V3 fechada com veredito `ACCEPTED_WITH_WARNINGS`. 13 achados
  (P0-2, P1-1, P1-4, P1-5, P1-6, P2-1 a P2-5, P1-3, P2-4, P0-1, P1-2) já
  corrigidos e documentados em `docs/historico/RELATORIO_CORRECAO_AUDITORIA_V3.md`.
- Artigo (`docs/Artigo_FEBRACE_revisado.docx`) já reescrito para não alegar
  Gyr/ejeção/alinhamento/"Ammonite" sem run real por trás.
- Únicas runs reais existentes: `experiment_angle_robustness_...` e
  `experiment_i_boundary_scan_...`, ambas **1 Myr**, REBOUND real. Nenhuma
  run secular (1e8 anos) ou de escala Gyr existe.
- Gate herdado (reexecute antes de confiar): `pytest -q` ~116 testes,
  `ruff check .` limpo, `python main.py doctor` ok.
- **Diagnóstico já feito, ainda não implementado**: o pipeline nunca roda
  nada em paralelo (zero `multiprocessing`/`concurrent.futures` em todo o
  código). Cada candidato, cada ponto de Monte Carlo, cada variação de
  ω9/i roda sequencialmente, mesmo sendo independente. Hardware de
  referência do usuário: 4 núcleos / 8 threads — ganho estimado ~4x sem
  tocar em física.
- Fonte de verdade de estado: `CONSOLIDADO_PLANET9_SCREENING_LAB.md` na raiz
  do projeto. Leia-o antes de qualquer ação — se ele divergir do código real
  (git log, testes), pare e reporte a divergência antes de prosseguir.

</contexto>

---

<objetivo>

Executar, em ordem estrita e sem pular etapas, o plano abaixo até o
repositório estar pronto para submissão — parando apenas nos pontos
explicitamente marcados como decisão do usuário (Categoria B).

</objetivo>

---

<classificacao_de_trabalho>

**Categoria A — implemente sem pedir permissão passo a passo.** Bugs,
testes ausentes, paralelização de loops já independentes, configuração de
ferramentas, tornar algo existente auditável. Sinalize antes de qualquer
comando que crie/apague arquivos fora de `/tmp`, mas não pare para perguntar
"posso corrigir isso?" — corrija, teste, prossiga.

**Categoria B — pare, apresente ≥2 opções com trade-offs, aguarde resposta
explícita.** O que o artigo pode alegar; mudar fórmula/threshold de métrica;
rodar integração em escala secular/Gyr; mudar critério de seleção/prioridade
de candidatos; variar ω9/Ω9/M0 por linha do Quadro 2. Nunca decida essas
sozinho, mesmo que pareça óbvio.

Classifique cada etapa abaixo (A ou B) em voz alta, em uma linha, antes de
começá-la.

</classificacao_de_trabalho>

---

<restricoes_invioláveis>

1. Nunca rode `secular.yaml` ou qualquer integração de horas/dias sem
   autorização explícita **nesta sessão** — autorização passada não vale.
2. Nunca misture no mesmo commit: paralelização + `exact_finish_time` +
   WHFast corrector + MEGNO + Rayleigh/Kuiper. Um commit por preocupação, na
   ordem da tarefa abaixo.
3. Nunca alegue resultado (Gyr, % alinhamento, tempo de ejeção, objeto
   nomeado) sem `run_manifest.json` real correspondente.
4. Nunca mude quem é selecionado/priorizado entre candidatos sem autorização
   — só torne cortes existentes auditáveis.
5. Nunca commite `__pycache__/`, zips internos, artefatos duplicados.
6. Nunca escolha sozinho um threshold, fórmula ou critério científico novo.
7. Toda mudança de comportamento vem com teste de regressão que falha antes
   e passa depois — sem teste, a etapa não terminou.
8. Antes de declarar qualquer etapa concluída, rode e cole a saída literal:
   ```
   python3 -m pytest -q
   python3 -m ruff check . --no-cache
   python3 main.py doctor
   ```
9. Nunca apague uma limitação documentada — só marque resolvido ou pendente.
10. Ao fechar cada etapa, atualize `CONSOLIDADO_PLANET9_SCREENING_LAB.md`
    (estado real, não histórico apagado) antes de seguir para a próxima.

</restricoes_invioláveis>

---

<eficiencia_de_tokens>

Métrica obrigatória, aplicável a toda sessão: **razão prosa:ação ≤ 1:4** —
para cada 4 linhas de código/diff/comando produzidas, no máximo 1 linha de
texto explicativo. Se você perceber que está escrevendo mais explicação do
que produzindo mudança real, isso é o sinal de parar de narrar e agir.

Regras concretas, não apenas princípio:

- **Raciocínio interno (chain-of-thought) antes de uma ação de código: no
  máximo ~40 palavras.** Se uma decisão já está resolvida por uma restrição
  numerada deste prompt (seção `<restricoes_invioláveis>`), não a rejustifique
  — cite o número (ex.: "conforme restrição 2") e prossiga direto para a ação.
- **Nunca reexplique o plano.** As etapas, DoD e restrições já estão
  definidas neste prompt — não parafraseie o que a etapa pede antes de
  executá-la; apenas execute e reporte o resultado no formato da seção
  `<formato_de_saida_por_sessao>`.
- **Nunca narre passos óbvios de ferramenta** ("vou agora editar o arquivo
  X para adicionar Y" seguido da edição). A edição em si já é a evidência —
  uma linha de contexto no máximo, se necessário.
- **Nunca repita conteúdo já visível** (arquivo que você acabou de ler,
  saída de comando que acabou de rodar) — referencie por nome/linha, não
  copie de volta.
- **Campo "O que mudou" no formato de saída é telegráfico**: `arquivo →
  mudança objetiva`, sem frases completas nem justificativa repetida do DoD.
- Exceção onde prosa longa é permitida e esperada: ao apresentar opções de
  **Categoria B** (trade-offs precisam ser claros) e ao reportar uma
  divergência entre CONSOLIDADO e código real. Fora desses dois casos, o
  padrão é ação > explicação.
- Se ao final da sessão a razão prosa:ação estimada ultrapassar 1:4, refaça
  o resumo cortando texto antes de entregar — não o conteúdo técnico.

</eficiencia_de_tokens>

---

<tarefa_ordenada>

Execute nesta sequência exata. Uma etapa por sessão, salvo pedido explícito
do usuário para encadear mais de uma. Não avance para a etapa N+1 sem a DoD
da etapa N fechada e o gate limpo.

**Etapa 0 — Higiene do workspace [Categoria A]**
Garantir `.gitignore` cobrindo `__pycache__/`, `*.pyc`, zips internos. Rodar
gate como baseline. Confirmar que não há artefato redundante no working
tree antes de tocar em código.

**Etapa 1 — Paralelização segura [Categoria A] — maior impacto/risco, fazer primeiro**
1. Criar utilitário de execução paralela por processo (`concurrent.futures`,
   stdlib, sem dependência nova), com `max_workers` configurável.
2. Aplicar primeiro em `planet9lab/run.py::_run_candidates_and_finalize`:
   workers retornam payloads puros; processo pai escreve
   cache/status/CSV/manifest em ordem determinística. Nunca escrever arquivo
   compartilhado dentro do worker.
3. Preservar fallback sequencial e a ordem final do ranking
   (`rows.sort(...)` já determinística — não alterar).
4. Threadar `workers` por toda a superfície pública: `execute_run`,
   `run_compare`, `run_smoke`, `run_screen`, `resume_run`,
   `run_montecarlo_scan`.
5. Só depois disso testado e fechado: aplicar em `planet9lab/montecarlo.py`
   (estágios 2 e 3).
6. Só depois disso testado e fechado: aplicar em `planet9lab/robustness.py`
   (leave-one-out, convergence, validate_top, null_models).
7. **Teste obrigatório**: modo sequencial vs. paralelo em `low.yaml`
   produzindo saída byte-idêntica (ranking, métricas, ordem de candidatos).
- **DoD**: gate limpo; teste sequencial-vs-paralelo passando; nenhuma
  fórmula física tocada; CONSOLIDADO atualizado.

**Etapa 2 — Consistência `exact_finish_time` [Categoria A, commit isolado da Etapa 1]**
Padronizar `sim.integrate(..., exact_finish_time=0)` no caminho não
checkpointado (`_run_rebound`), igualando ao checkpointado
(`run_branch_checkpointed`). Isto muda levemente trajetórias numéricas —
escrever teste de regressão numérica que documenta a magnitude do delta.
- **DoD**: gate limpo; delta numérico documentado; commit isolado.

**Etapa 3 — Benchmark real de hardware [Categoria A, mas depende do usuário rodar na máquina real]**
Executar `scripts/benchmark_integration_cost.py` na máquina real do usuário.
Atualizar `results/hardware_benchmark.json` com proveniência explícita
(hardware, data, antes/depois da Etapa 1). Nunca usar número de sandbox como
referência de prazo de artigo daqui pra frente.
- **DoD**: arquivo atualizado com metadado de proveniência real.

**Etapa 4 — MEGNO experimental [Categoria A na implementação / Categoria B no uso]**
Implementar `sim.init_megno(seed=...)` como métrica opcional, seed fixa, sem
alterar o funil principal. **Pare e pergunte** antes de usar MEGNO como
argumento de estabilidade Gyr no artigo — não calibrado ainda é Categoria B.
- **DoD**: métrica testada isoladamente; documentação explícita de que é
  indicador auxiliar não calibrado.

**Etapa 5 — Rayleigh Z / Kuiper [Categoria B de escopo, A de implementação]**
Só iniciar com a Etapa 1 versionada e resultados atuais estáveis. Implementar
como opção configurável ao lado dos thresholds ad hoc atuais — comparar lado
a lado sobre as runs reais existentes. Não promover a padrão sem aprovação
explícita (isso muda classificação de candidato = Categoria B).
- **DoD**: implementação testada + comparação lado a lado, sem virar padrão
  automaticamente.

**Horizonte 1 — decisões estruturais [todas Categoria B — parar e perguntar antes de continuar para o Horizonte 2]**
- 1.1: ω9/Ω9/M0 fixos ou variando por linha do Quadro 2? (muda dado de
  entrada de 6 das 7 linhas — decidir antes de rodar mais candidatos)
- 1.2: depende da Etapa 3 fechada.
- 1.3: cruzar os 13 ETNOs com a Tabela A1 de De la Fuente Marcos & De la
  Fuente Marcos 2014 (arXiv:1406.0715), campo a campo — baixo custo, nunca
  feito.
- 1.4: estratégia final de versionamento de `runs/` (manifests vs. runs
  completas vs. nada) — decisão do usuário.

**Horizonte 2 — run secular real [Categoria B, maior custo — só depois do Horizonte 1 fechado]**
Requer autorização explícita e recente (restrição 1). Critério de sucesso:
cada linha da Tabela 2 do artigo com `run_manifest.json` real por trás.

**Horizonte 3 — Estágios 4/5 do funil [Categoria B, trabalho substancial]**
Hamiltoniano secular quadrupolo/octupolo (estágio 4) e detectabilidade
(estágio 5). Não iniciar sem decisão explícita de que vale o investimento
antes da submissão.

**Horizonte 4 — ampliação metodológica opcional [Categoria B]**
Surrogate ML (só após volume real de dados do estágio 2/3, ou seja, após o
Horizonte 2) e revisão de modelos nulos.

**Horizonte 5 — fechamento para submissão [A de forma, B de conteúdo]**
`CHANGELOG_V3.md` + `RELATORIO_EVOLUCAO_V3.md`; `docs/LIMITACOES.md` final;
revisão ABNT separada de qualquer mudança de conteúdo científico.

</tarefa_ordenada>

---

<formato_de_saida_por_sessao>

Ao final de cada sessão, entregue exatamente neste formato, sem omitir
nenhum campo:

```
## Etapa executada: [nome/número]
## Classificação: [A ou B — justificativa em 1 linha]

### O que mudou
[arquivo → o que foi alterado, objetivamente]

### Testes adicionados/alterados
[nome → o que prova → resultado antes/depois]

### Gate
pytest: [saída literal]
ruff:   [saída literal]
doctor: [saída literal]

### CONSOLIDADO atualizado
[resumo do diff nas seções 3/4/6]

### Pendências de Categoria B (se houver)
[opção 1 c/ trade-offs | opção 2 c/ trade-offs | PENDENTE]

### Próxima etapa
[nome/número exato da lista acima]
```

Nunca declare uma etapa concluída sem este bloco preenchido com dados reais
(não resumos otimistas do tipo "tudo passou"). Aplique a razão prosa:ação de
`<eficiencia_de_tokens>` também aqui — este bloco é dado, não redação.

</formato_de_saida_por_sessao>

---

<primeira_acao>

Comece agora pela **Etapa 0**: leia `CONSOLIDADO_PLANET9_SCREENING_LAB.md`
por completo, confirme que bate com o estado real do código (`git log`,
estrutura de arquivos), rode o gate como baseline, garanta o `.gitignore`, e
entregue o bloco de fechamento da Etapa 0 antes de iniciar a Etapa 1.

</primeira_acao>
