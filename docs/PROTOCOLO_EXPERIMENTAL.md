# Protocolo Experimental V1

Pergunta científica:

> O modelo com P9 melhora as métricas dinâmicas dos ETNOs em relação ao modelo sem P9?

Passos:

1. Carregar catálogo canônico de ETNOs.
2. Carregar gigantes no epoch definido.
3. Validar candidatos, orçamento, pesos e protocolo.
4. Para cada candidato, executar controle sem P9.
5. Para o mesmo candidato, executar integração com P9.
6. Calcular métricas e `delta_dynamic_score`.
7. Aplicar blockers e policy de conclusão.
8. Gerar artefatos, hashes, relatório e auditoria.

Métricas e pesos não podem ser alterados após uma run sem nova run ou rescore documentado.

