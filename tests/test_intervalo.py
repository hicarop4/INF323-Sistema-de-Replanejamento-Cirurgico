import pytest

from ccreplan.dominio.tempo import Intervalo
from tests.construtor import hora, intervalo


def test_duracao_em_minutos():
    assert intervalo("08:00", "09:30").duracao_min == 90


def test_fim_deve_ser_depois_do_inicio():
    with pytest.raises(ValueError):
        Intervalo(hora("09:00"), hora("09:00"))


def test_a_partir_de_um_inicio_e_uma_duracao():
    assert Intervalo.a_partir(hora("13:00"), 45) == intervalo("13:00", "13:45")


@pytest.mark.parametrize(
    ("outro", "esperado"),
    [
        (("08:30", "09:30"), True),
        (("07:00", "08:01"), True),
        (("09:00", "10:00"), False),  # encosta no fim: não sobrepõe
        (("07:00", "08:00"), False),  # encosta no início: não sobrepõe
    ],
)
def test_sobreposicao(outro, esperado):
    assert intervalo("08:00", "09:00").sobrepoe(intervalo(*outro)) is esperado


def test_contem():
    turno = intervalo("07:00", "12:00")
    assert turno.contem(intervalo("07:00", "12:00"))
    assert not turno.contem(intervalo("11:00", "12:30"))


def test_deslocado_mantem_a_duracao():
    assert intervalo("08:00", "09:00").deslocado(20) == intervalo("08:20", "09:20")


def test_estendido_aumenta_so_o_fim():
    assert intervalo("08:00", "09:00").estendido(30) == intervalo("08:00", "09:30")
