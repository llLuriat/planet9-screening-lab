# Critério Formal de Seleção dos ETNOs

O catálogo V1 deve registrar por que cada objeto entrou ou não entrou no conjunto de ETNOs analisado. O objetivo é impedir que o catálogo pareça escolhido manualmente para favorecer um resultado.

Campos obrigatórios no catálogo:

- `selection_included`
- `selection_reason`
- `selection_notes`

Regra exemplo do catálogo V1:

- Incluir objetos transnetunianos extremos de fixture com `a_au > 150` e periélio suficientemente externo para o teste dinâmico simplificado.
- Excluir objetos de controle ou objetos abaixo do limiar ETNO, registrando explicitamente o motivo em `selection_reason`.

O V1 usa dados de exemplo para validar o pipeline. Catálogos científicos reais devem preservar os mesmos campos de auditoria.
