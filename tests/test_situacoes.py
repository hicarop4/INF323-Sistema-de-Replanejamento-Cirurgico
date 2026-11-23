"""Situação das cirurgias atualizada pelo horário."""

import pytest

from ccreplan.dominio.modelos import Situacao
from tests.construtor import Cenario, hora


@pytest.mark.parametrize(
    ("agora", "esperada"),
    [
        ("07:00", Situacao.AGENDADA),  # ainda não começou
        ("08:00", Situacao.EM_ANDAMENTO),  # começou agora
        ("08:59", Situacao.EM_ANDAMENTO),
        ("09:00", Situacao.CONCLUIDA),  # terminou
    ],
)
def test_cirurgia_agendada_muda_de_situacao_com_o_horario(agora, esperada):
    centro = Cenario().com_cirurgia("c1", "08:00").construir()
    assert centro.com_situacoes_em(hora(agora)).cirurgia("c1").situacao is esperada


@pytest.mark.parametrize("situacao", [Situacao.ADIADA, Situacao.CANCELADA])
def test_adiada_e_cancelada_nao_mudam_com_o_horario(situacao):
    centro = Cenario().com_cirurgia("c1", "08:00", situacao=situacao).construir()
    assert centro.com_situacoes_em(hora("10:00")).cirurgia("c1").situacao is situacao


def test_em_andamento_fica_concluida_quando_passa_do_fim():
    centro = Cenario().com_cirurgia("c1", "08:00", situacao=Situacao.EM_ANDAMENTO).construir()
    assert centro.com_situacoes_em(hora("09:30")).cirurgia("c1").situacao is Situacao.CONCLUIDA
