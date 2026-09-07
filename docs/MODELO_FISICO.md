# Modelo Físico V1

O V1 usa REBOUND como integrador N-corpos real no caminho principal de `screen`, `smoke` e `compare`.

Modelo mínimo:

- Sol com massa `1.0` em unidades de massa solar.
- Gigantes Júpiter, Saturno, Urano e Netuno como partículas massivas.
- Candidato P9 como partícula massiva quando `include_p9=true`.
- ETNOs como partículas sem massa.
- Unidades: ano, AU e massa solar.
- Constante gravitacional: `G = 4*pi^2`.
- Integrador padrão do screen: WHFast.

O controle pareado é obrigatório:

- Uma integração com P9.
- Uma integração sem P9.
- Mesmos ETNOs, gigantes, budget e seed.

O V1 não determina a órbita real do Planeta 9. Ele só testa se candidatos dentro de uma região de parâmetros melhoram métricas dinâmicas em relação ao controle sem P9.

