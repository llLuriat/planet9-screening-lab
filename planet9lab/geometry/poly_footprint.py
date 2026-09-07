"""Primitivas de footprint poligonal, portadas do OSSOS SurveySimulator.

As funções neste módulo são diagnósticos standalone: NÃO estão integradas ao
pipeline principal do planet9lab (selection_bias / cli / policy) nesta etapa.

Fontes do código-fonte Fortran original (clone READ-ONLY):
    D:\\_tmp_ossos_survey\\fortran\\F95\\getsur.f95
        create_poly : linhas ~220-223 (converte offsets radiais em vértices absolutos)
    D:\\_tmp_ossos_survey\\fortran\\F95\\poly_lib.f95
        point_in_polygon    : linhas 21-91  (método do quadrante / "walk sum")
        calc_walk_summand   : linhas 93-180 (somando por aresta; -100 = sobre aresta)
        check_polygon       : linha ~182    (fechamento do anel: vértice n+1 = vértice 1)

Atribuição da geometria dos blocos OSSOS 2013A (centro, offsets, filling_factor):
    planet9lab/data/ossos_2013a_blocks.py (extraído de pointings.list e *.eff do
    OSSOS SurveySimulator, commit a1fcf1bfc146b7b72654d65d6789c59790e3cbb4).

Convenções de unidade (FIÉIS ao Fortran original — NÃO inventadas aqui):
    - TODOS os ângulos de entrada/saída estão em RADIANOS (o Fortran opera em rad:
      dcos espera radianos; a pesquisa usa (RA,Dec) em radianos, cf. docstring de
      ossos_2013a_blocks.py). Os dados em ossos_2013a_blocks.py estão em GRAUS e
      devem ser convertidos com math.radians() no ponto de chamada.
    - O polígono é representado como uma lista de tuplas (x, y) = (RA, Dec).
    - O anel é FECHADO: o último vértice repete o primeiro (n+1 vértices para n
      arestas), como em t_polygon após check_polygon.

Retorno de point_in_polygon (idêntico ao Fortran):
    n (número de vértices/arestas) : ponto DENTRO
    1                              : ponto sobre BORDA
    0                              : ponto FORA
"""

from __future__ import annotations

import math
from typing import Sequence

__all__ = ["create_poly", "point_in_polygon"]


def create_poly(
    ra_center: float,
    dec_center: float,
    offsets: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Converte offsets de cantos em vértices absolutos do polígono (anel fechado).

    Porta getsur.f95::create_poly (linhas ~220-223) + fechamento do anel
    (check_polygon, poly_lib.f95:~182).

    Semântica (FIEL ao Fortran):
        y(j) = dec_center + offset_y(j)                       (soma linear em Dec)
        x(j) = ra_center + offset_x(j) / cos(y(j))            (correção de cos(Dec);
                                                               cosseno avaliado no
                                                               Dec ABSOLUTO do próprio
                                                               canto já atualizado, e
                                                               não no Dec do centro)

    Args:
        ra_center   : RA do centro do bloco, em RADIANOS.
        dec_center  : Dec do centro do bloco, em RADIANOS.
        offsets     : sequência de (offset_x, offset_y) por canto, em RADIANOS.
                      ORDEM deve ser consistente (horária ou anti-horária).

    Returns:
        Lista de (RA, Dec) em RADIANOS, fechada (últico vértice == primeiro).

    Raises:
        ValueError: se offsets estiver vazio.
        ZeroDivisionError: se cos(y(j)) == 0 (canto no polo, dec == ±90°).
    """
    if not offsets:
        raise ValueError("offsets deve conter ao menos um canto")

    vertices: list[tuple[float, float]] = []
    for offset_x, offset_y in offsets:
        y = dec_center + offset_y
        x = ra_center + offset_x / math.cos(y)
        vertices.append((x, y))

    # Fechamento do anel: repete o 1o vértice (check_polygon, poly_lib.f95:~182).
    vertices.append(vertices[0])
    return vertices


def _calc_walk_summand(
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> int:
    """Calcula o somando de caminhada para uma aresta (p1 -> p2).

    Porta FIELMENTE calc_walk_summand (poly_lib.f95:93-180). O algoritmo conta
    cruzamentos dos eixos pelo segmento, a partir da origem (ponto já trasladado).

    NOTA sobre fidelidade: no bloco de cruzamento do eixo y (segundo `if`), a
    verificação "origem sobre a aresta" reutiliza x_y0 JÁ MODIFICADO pelo bloco
    anterior (x_y0 = x_y0*(p2(y) - p1(y))). Este é o comportamento EXATO do
    Fortran original e é preservado aqui — não é um bug da portagem.

    Args:
        p1, p2 : pontos (x, y) da aresta, com o ponto-teste já trasladado à origem.

    Returns:
        +1 (sentido horário), -1 (anti-horário), 0 (sem cruzamento),
        +2/-2 (cruzamento diagonal), ou -100 (origem sobre a aresta).
    """
    x1, y1 = p1
    x2, y2 = p2

    # Parâmetro de interseção com o eixo vertical (poly_lib.f95:139-143).
    if x1 != x2:
        ty = x1 / (x1 - x2)
    else:
        ty = y1 / (y1 - y2)

    # Parâmetro de interseção com o eixo horizontal (poly_lib.f95:146-150).
    if y1 != y2:
        tx = y1 / (y1 - y2)
    else:
        tx = ty

    # Posição das interseções com os eixos (poly_lib.f95:153-154).
    x_y0 = x1 + tx * (x2 - x1)
    y_x0 = y1 + ty * (y2 - y1)

    summand = 0

    # Cruzamento do eixo x (poly_lib.f95:157-165).
    if 0.0 <= tx < 1.0:
        if x_y0 == 0.0 and y_x0 == 0.0:
            return -100
        x_y0 = x_y0 * (y2 - y1)
        if x_y0 != 0.0:
            summand += 1 if x_y0 > 0 else -1

    # Cruzamento do eixo y (poly_lib.f95:168-176).
    # ATENÇÃO: x_y0 aqui é o valor JÁ MODIFICADO pelo bloco acima (fidelidade).
    if 0.0 <= ty < 1.0:
        if x_y0 == 0.0 and y_x0 == 0.0:
            return -100
        y_x0 = y_x0 * (x1 - x2)
        if y_x0 != 0.0:
            summand += 1 if y_x0 > 0 else -1

    return summand


def point_in_polygon(
    point: tuple[float, float],
    poly: Sequence[tuple[float, float]],
) -> int:
    """Testa se um ponto está dentro, fora ou na borda de um polígono.

    Porta point_in_polygon (poly_lib.f95:21-91) — método do quadrante
    ("walk sum"). O ponto é trasladado à origem e, para cada aresta, soma-se o
    retorno de calc_walk_summand. Soma final ±4 => dentro; -100 em qualquer
    aresta => sobre a borda.

    Args:
        point : (RA, Dec) do ponto-teste, em RADIANOS.
        poly  : polígono como sequência de (RA, Dec) em RADIANOS, em anel FECHADO
                (último vértice == primeiro, n+1 vértices para n arestas). Pode ser
                produzido por create_poly().

    Returns:
        n (número de arestas) : ponto DENTRO do polígono
        1                     : ponto sobre a BORDA do polígono
        0                     : ponto FORA do polígono
    """
    n = len(poly) - 1  # anel fechado: n+1 vértices para n arestas (poly_lib.f95:72)
    if n <= 0:
        return 0

    px, py = point
    walk_sum = 0

    for i in range(n):
        # Traslada o ponto à origem para a aresta (poly_lib.f95:65-68).
        p1 = (poly[i][0] - px, poly[i][1] - py)
        p2 = (poly[i + 1][0] - px, poly[i + 1][1] - py)
        walk = _calc_walk_summand(p1, p2)
        if walk == -100:
            return 1
        walk_sum += walk

    # Verificação final (poly_lib.f95:84-88).
    if abs(walk_sum) == 4:
        return n
    return 0

