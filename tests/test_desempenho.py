"""As opções devem ser geradas em até 30 segundos."""

from time import perf_counter

from ccreplan.dominio.modelos import Funcao
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia, analisar
from ccreplan.replanejamento.opcoes import gerar_opcoes
from tests.construtor import Cenario, intervalo

FUNCOES = (Funcao.CIRURGIAO, Funcao.ANESTESISTA, Funcao.ENFERMEIRO)
HORARIOS = ["07:00", "08:30", "10:00", "11:30", "13:00", "14:30", "16:00"]
LIMITE_SEGUNDOS = 30


def dia_cheio() -> Cenario:
    """Plano Básico: as 3 salas ocupadas o dia todo (21 cirurgias), uma equipe por sala."""
    cenario = Cenario().com_estoque("pinca", 6)
    for sala in cenario.salas:
        equipe = tuple(f"{funcao.name}-{sala}" for funcao in FUNCOES)
        for pid, funcao in zip(equipe, FUNCOES, strict=True):
            cenario.com_profissional(pid, f"{funcao.value} {sala}", funcao)
        for n, inicio in enumerate(HORARIOS):
            cenario.com_cirurgia(f"{sala}-{n}", inicio, sala=sala, equipe=equipe)
    return cenario


def test_opcoes_geradas_em_ate_30_segundos_num_dia_cheio():
    atraso = Ocorrencia(TipoOcorrencia.ATRASO_CIRURGIA, "S1-0", intervalo("08:00", "08:40"))
    centro = dia_cheio().construir()

    inicio = perf_counter()
    opcoes = gerar_opcoes(analisar(atraso, centro))
    duracao = perf_counter() - inicio

    assert opcoes
    assert duracao < LIMITE_SEGUNDOS
