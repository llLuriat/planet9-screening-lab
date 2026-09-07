"""Caracterização dos blocos OSSOS 2013A-E e 2013A-O (geometria + eficiência).

FONTE DOS VALORES (copiados verbatim, sem arredondamento, dos arquivos originais):
    Repositório: OSSOS SurveySimulator -- https://github.com/OSSOS/SurveySimulator
    Commit de referência do clone usado para extração:
        a1fcf1bfc146b7b72654d65d6789c59790e3cbb4 (2023-09-03)
    Arquivos de origem:
        fortran/F95/SS_Input_Formats/pointings.list  (centro, época,
            filling_factor, obs_code e cantos do polígono de cada bloco)
        fortran/F95/SS_Input_Formats/2013AE.eff      (eficiência do bloco 2013A-E)
        fortran/F95/SS_Input_Formats/2013AO.eff      (eficiência do bloco 2013A-O)
    Licença da fonte: European Union Public Licence v1.1 (EUPL v1.1), declarada
    no README.md do repositório (eupl1.1.-en_0_0.pdf / eupl1.1.-licence-en_0.pdf).

CITAÇÃO OBRIGATÓRIA AO USAR ESTES DADOS (exigida pelo README.md da fonte):
    Bannister et al. (2016), AJ, 152, 70   (blocos 2013A do OSSOS)
    Bannister et al. (2018), ApJS, 236, 18 (caracterização do OSSOS)

LIMITAÇÃO EXPLÍCITA: este arquivo contém apenas 2 blocos de 2013A -- NÃO
representa a cobertura completa da survey OSSOS de 8 anos.

INTERPRETAÇÃO GEOMÉTRICA DOS CANTOS (lida do código-fonte da fonte, não assumida):
    Parsing (getsur.f95::read_sur, linhas 705-723): os n cantos são lidos em
    GRAUS e convertidos para radianos (x = 1a coluna, y = 2a coluna de cada
    linha de canto). ATENCAO A UNIDADE DO CENTRO: RA com dois-pontos
    (ex. 14:15:28.89) e sexagesimal em HORAS e e convertido para graus por
    hms() seguido de ra*15 (getsur.f95:708-715); DEC com dois-pontos e
    sexagesimal em GRAUS. Conversao para vertices absolutos no ceu
    (getsur.f95::create_poly, linhas 220-223):
        Dec_canto = Dec_centro + y                    (offset linear em Dec)
        RA_canto  = RA_centro + x / cos(Dec_canto)    (flat-sky com correção de
        cos(Dec); o cosseno é avaliado no Dec ABSOLUTO do próprio canto, já
        atualizado, e não no Dec do centro). Sem rotação por position angle e
        sem projeção gnomônica; o anel é fechado repetindo o 1o canto
        (check_polygon, poly_lib.f95:182).
    Teste de pertencimento (surveysub.f95:251-252 e 300; poly_lib.f95:21-91):
        p = (RA, Dec) do objeto em radianos; point_in_polygon usa o método do
        quadrante ("walk sum") no plano (x=RA, y=Dec); retorna n (dentro), 1
        (na borda) ou 0 (fora). Sem tratamento de wraparound de RA (irrelevante
        para RA ~214 graus e ~240 graus destes dois blocos).

SIGNIFICADO DE filling_factor (getsur.f95:753; surveysub.f95:208 e 300-317):
    NÃO é geométrico e NÃO altera o polígono: é a probabilidade de aceitação
    Monte Carlo aplicada APÓS o teste ponto-em-polígono:
        in_poly = point_in_polygon(p, poly); se in_poly > 0:
        random = ran3(seed); objeto aceito se random <= ff
    (comentário original: "Check for chip gaps, ..., the filling factor.").

FORMA FUNCIONAL "square" (effut.f95:144-154; README.formats da fonte):
    eta(m) = eff_max                                            se m < 21
    eta(m) = (eff_max - c*(m-21)**2) / (1 + exp((m - M_0)/sig))  se m >= 21
    square_param = (eff_max, c, M_0, sig); fora da faixa "rates", eta = 0.
    As faixas de "rates" estão em arcsec/hora (o simulador converte para
    rad/dia em read_eff, getsur.f95:436-437).

Este módulo é apenas dados citados: nada no pipeline o consome ainda.
"""

OSSOS_2013A_BLOCKS: dict[str, dict[str, object]] = {
    "2013A-E": {
        # pointings.list: "poly 4 14:15:28.89 -12:32:28.5 2456391.86686 0.9079 500 2013AE.eff"
        "center_ra_deg": 213.870375,  # 14:15:28.89 em HORAS sexagesimais = 14.258025 h * 15
        "center_dec_deg": -12.5412500,  # -12:32:28.5 em graus sexagesimais = -12.54125 deg
        "epoch_jd": 2456391.86686,
        "filling_factor": 0.9079,
        "obs_code": 500,
        # Cantos exatamente como no pointings.list: (x_leste-oeste_deg, y_dec_deg)
        "corner_offsets_deg": [
            (-3.5, -0.434889),
            (-3.5, 2.565111),
            (3.5, 0.473417),
            (3.5, -2.526583),
        ],
        # 2013AE.eff: 3 faixas de taxa, todas com função "square".
        "efficiency": [
            {
                "rates_arcsec_per_hour": (0.50, 8.00),
                "function": "square",
                "square_param": (0.887741923, 2.76305359e-02, 24.1423416, 0.153656587),
                "mag_lim": 24.09,
            },
            {
                "rates_arcsec_per_hour": (8.00, 11.00),
                "function": "square",
                "square_param": (0.895575285, 2.31122747e-02, 24.0048294, 0.157101125),
                "mag_lim": 23.85,
            },
            {
                "rates_arcsec_per_hour": (11.00, 15.00),
                "function": "square",
                "square_param": (0.865791440, 2.12179236e-02, 23.8810692, 0.155520618),
                "mag_lim": 23.73,
            },
        ],
    },
    "2013A-O": {
        # pointings.list: "poly 4 15:58:01.35 -12:19:54.2 2456420.95956 0.9055 500 2013AO.eff"
        "center_ra_deg": 239.505625,  # 15:58:01.35 em HORAS sexagesimais = 15.96704167 h * 15
        "center_dec_deg": -12.331722222222222,  # -12:19:54.2 em graus sexagesimais
        "epoch_jd": 2456420.95956,
        "filling_factor": 0.9055,
        "obs_code": 500,
        # Cantos exatamente como no pointings.list: (x_leste-oeste_deg, y_dec_deg)
        "corner_offsets_deg": [
            (-3.5, -0.862333),
            (-3.5, 2.137667),
            (3.5, 0.915750),
            (3.5, -2.084250),
        ],
        # 2013AO.eff: 3 faixas de taxa, todas com função "square". As faixas do
        # bloco O são diferentes das do bloco E (0.50-7.00, 7.00-10.00, 10.00-15.00).
        "efficiency": [
            {
                "rates_arcsec_per_hour": (0.50, 7.00),
                "function": "square",
                "square_param": (0.841375411, 2.05407962e-02, 24.5497284, 0.110739127),
                "mag_lim": 24.40,
            },
            {
                "rates_arcsec_per_hour": (7.00, 10.00),
                "function": "square",
                "square_param": (0.877626657, 1.88417193e-02, 24.4186745, 0.121682763),
                "mag_lim": 24.26,
            },
            {
                "rates_arcsec_per_hour": (10.00, 15.00),
                "function": "square",
                "square_param": (0.863873243, 1.87772699e-02, 24.2575226, 0.145261303),
                "mag_lim": 24.10,
            },
        ],
    },
}
