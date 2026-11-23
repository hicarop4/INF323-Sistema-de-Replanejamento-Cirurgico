"""Registrar ocorrência: o sistema identifica sozinho as cirurgias afetadas."""

from ccreplan.dominio.modelos import Situacao
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia, analisar
from tests.construtor import Cenario, intervalo

OUTRA_EQUIPE = ("cir2", "anest2", "enf2")


def afetadas(cenario, ocorrencia):
    return [c.id for c in analisar(ocorrencia, cenario.construir()).afetadas]


def test_ausencia_de_profissional_afeta_so_as_cirurgias_dele_no_periodo():
    cenario = Cenario().com_cirurgia("c1", "08:00").com_cirurgia("c2", "11:00")
    cenario.com_cirurgia("c3", "11:00", sala="S2", equipe=OUTRA_EQUIPE)
    ausencia = Ocorrencia(
        TipoOcorrencia.AUSENCIA_PROFISSIONAL, "anest1", intervalo("10:00", "12:00")
    )
    assert afetadas(cenario, ausencia) == ["c2"]


def test_sala_indisponivel_afeta_as_cirurgias_da_sala_no_periodo():
    cenario = Cenario().com_cirurgia("c1", "08:00").com_cirurgia("c2", "10:00")
    cenario.com_cirurgia("c3", "10:00", sala="S2", equipe=OUTRA_EQUIPE)
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S1", intervalo("09:30", "11:30"))
    assert afetadas(cenario, sala) == ["c2"]


def test_instrumento_indisponivel_afeta_quem_fica_sem_instrumento():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    falta = Ocorrencia(
        TipoOcorrencia.INSTRUMENTO_INDISPONIVEL, "pinca", intervalo("07:00", "12:00"), quantidade=3
    )
    assert afetadas(cenario, falta) == ["c1"]


def test_paciente_indisponivel():
    cenario = Cenario().com_cirurgia("c1", "08:00", paciente="p1").com_cirurgia("c2", "10:00")
    paciente = Ocorrencia(TipoOcorrencia.PACIENTE_INDISPONIVEL, "p1", intervalo("07:30", "09:00"))
    assert afetadas(cenario, paciente) == ["c1"]


def test_atraso_afeta_a_cirurgia_seguinte_da_sala_e_nao_a_propria():
    cenario = Cenario().com_cirurgia("c1", "08:00").com_cirurgia("c2", "09:30", equipe=OUTRA_EQUIPE)
    atraso = Ocorrencia(TipoOcorrencia.ATRASO_CIRURGIA, "c1", intervalo("09:00", "09:20"))
    assert afetadas(cenario, atraso) == ["c2"]


def test_cirurgia_atrasada_passa_a_ocupar_a_sala_por_mais_tempo():
    centro = Cenario().com_cirurgia("c1", "08:00").construir()
    atraso = Ocorrencia(TipoOcorrencia.ATRASO_CIRURGIA, "c1", intervalo("09:00", "09:20"))
    atrasada = analisar(atraso, centro).centro.cirurgia("c1")
    assert atrasada.horario == intervalo("08:00", "09:20")
    assert atrasada.situacao is Situacao.EM_ANDAMENTO


def test_ocorrencia_que_nao_atinge_ninguem():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    ausencia = Ocorrencia(
        TipoOcorrencia.AUSENCIA_PROFISSIONAL, "anest2", intervalo("07:00", "19:00")
    )
    assert afetadas(cenario, ausencia) == []


def test_cirurgia_que_ja_tinha_problema_nao_e_atribuida_a_ocorrencia():
    cenario = Cenario().com_cirurgia("c1", "08:00", equipe=("cir1", "enf1"))
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S2", intervalo("07:00", "19:00"))
    assert afetadas(cenario, sala) == []


def test_descricao_do_tipo_para_a_tela():
    assert TipoOcorrencia.AUSENCIA_PROFISSIONAL.value == "Ausência de profissional"
