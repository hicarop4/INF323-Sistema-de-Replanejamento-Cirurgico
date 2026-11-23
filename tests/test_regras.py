"""Regras de validação do agendamento, reaproveitadas pelo replanejamento ."""

from datetime import time, timedelta

from ccreplan.dominio.modelos import Situacao, TipoRecurso, Turno
from ccreplan.dominio.regras import (
    RegraConflitoDeHorario,
    RegraEquipe,
    RegraHigienizacao,
    RegraInstrumentos,
    RegraPaciente,
    RegraSala,
    Validador,
)
from ccreplan.dominio.tempo import Intervalo
from tests.construtor import Cenario, hora, intervalo


def verificar(regra, cenario, cid="c1"):
    centro = cenario.construir()
    return regra.verificar(centro.cirurgia(cid), centro)


def test_cirurgia_completa_e_valida_em_todas_as_regras():
    centro = Cenario().com_cirurgia("c1").construir()
    resultado = Validador().verificar(centro.cirurgia("c1"), centro)
    assert resultado.valida
    assert resultado.violacoes == ()

def test_falta_de_profissional_exigido_pelo_procedimento():
    resultado = verificar(RegraEquipe(), Cenario().com_cirurgia("c1", equipe=("cir1", "enf1")))
    assert not resultado.valida
    assert "Falta anestesista na equipe" in resultado.violacoes


def test_profissional_fora_do_turno():
    cenario = Cenario().com_turno("anest1", "07:00", "08:30").com_cirurgia("c1", "08:00")
    assert "Dr. Paulo Mendes fora do turno" in verificar(RegraEquipe(), cenario).violacoes


def test_profissional_com_ausencia_registrada():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    cenario.indisponivel(TipoRecurso.PROFISSIONAL, "anest1", intervalo("08:30", "10:00"))
    assert "Dr. Paulo Mendes indisponível" in verificar(RegraEquipe(), cenario).violacoes


def test_turno_terminando_junto_com_a_cirurgia_e_restricao_no_limite():
    cenario = Cenario().com_turno("anest1", "07:00", "09:00").com_cirurgia("c1", "08:00")
    resultado = verificar(RegraEquipe(), cenario)
    assert resultado.valida
    assert "turno de Dr. Paulo Mendes" in resultado.limites

def test_sala_ocupada_no_mesmo_intervalo():
    cenario = Cenario().com_cirurgia("c0", "07:30", equipe=("cir2", "anest2", "enf2"))
    cenario.com_cirurgia("c1", "08:00")
    assert "Sala 01 ocupada" in verificar(RegraConflitoDeHorario(), cenario).violacoes


def test_profissional_em_duas_cirurgias_ao_mesmo_tempo():
    cenario = Cenario().com_cirurgia("c0", "08:30", sala="S2").com_cirurgia("c1", "08:00")
    resultado = verificar(RegraConflitoDeHorario(), cenario)
    assert "Dra. Helena Rocha já está em outra cirurgia" in resultado.violacoes


def test_paciente_em_duas_cirurgias_ao_mesmo_tempo():
    cenario = Cenario().com_cirurgia(
        "c0", "08:30", sala="S2", paciente="p1", equipe=("cir2", "anest2", "enf2")
    )
    cenario.com_cirurgia("c1", "08:00", paciente="p1")
    assert (
        "Paciente P1 já está em outra cirurgia"
        in verificar(RegraConflitoDeHorario(), cenario).violacoes
    )


def test_cirurgia_cancelada_nao_ocupa_recursos():
    cenario = (
        Cenario()
        .com_cirurgia("c0", "08:00", situacao=Situacao.CANCELADA)
        .com_cirurgia("c1", "08:00")
    )
    assert verificar(RegraConflitoDeHorario(), cenario).valida


# Sala permitida pelo procedimento e não bloqueada; paciente disponível.
def test_sala_nao_permitida_para_o_procedimento():
    cenario = Cenario().com_cirurgia("c1", sala="S9")
    assert "Procedimento não pode ser feito na sala S9" in verificar(RegraSala(), cenario).violacoes


def test_sala_bloqueada():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    cenario.indisponivel(TipoRecurso.SALA, "S1", intervalo("08:30", "10:30"))
    assert "Sala 01 indisponível" in verificar(RegraSala(), cenario).violacoes


def test_paciente_indisponivel():
    cenario = Cenario().com_cirurgia("c1", "08:00", paciente="p1")
    cenario.indisponivel(TipoRecurso.PACIENTE, "p1", intervalo("07:00", "08:30"))
    assert "Paciente P1 indisponível" in verificar(RegraPaciente(), cenario).violacoes


# NF10.3 Instrumentos
def test_instrumentos_insuficientes_somando_cirurgias_simultaneas():
    cenario = Cenario().com_estoque("pinca", 3)
    cenario.com_cirurgia("c0", "08:00", sala="S2", equipe=("cir2", "anest2", "enf2"))
    cenario.com_cirurgia("c1", "08:30")
    assert "Pinça Kelly insuficiente" in verificar(RegraInstrumentos(), cenario).violacoes


def test_instrumento_indisponivel_reduz_o_estoque():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    cenario.indisponivel(
        TipoRecurso.INSTRUMENTO, "pinca", intervalo("07:00", "12:00"), quantidade=3
    )
    assert "Pinça Kelly insuficiente" in verificar(RegraInstrumentos(), cenario).violacoes


def test_estoque_exato_e_restricao_no_limite():
    resultado = verificar(RegraInstrumentos(), Cenario().com_estoque("pinca", 2).com_cirurgia("c1"))
    assert resultado.valida
    assert "Pinça Kelly no limite" in resultado.limites


def test_cirurgia_comeca_antes_do_fim_da_higienizacao_anterior():
    cenario = Cenario().com_cirurgia("c0", "07:00", equipe=("cir2", "anest2", "enf2"))
    cenario.com_cirurgia("c1", "08:15")
    assert (
        "Higienização da Sala 01 não cumprida" in verificar(RegraHigienizacao(), cenario).violacoes
    )


def test_cirurgia_atrapalha_a_higienizacao_antes_da_proxima():
    cenario = Cenario().com_cirurgia("c2", "09:15", equipe=("cir2", "anest2", "enf2"))
    cenario.com_cirurgia("c1", "08:00")
    assert (
        "Higienização da Sala 01 não cumprida" in verificar(RegraHigienizacao(), cenario).violacoes
    )


def test_higienizacao_com_tempo_exato_e_restricao_no_limite():
    cenario = Cenario().com_cirurgia("c0", "07:00", equipe=("cir2", "anest2", "enf2"))
    cenario.com_cirurgia("c1", "08:30")
    resultado = verificar(RegraHigienizacao(), cenario)
    assert resultado.valida
    assert "limpeza da Sala 01" in resultado.limites


# Turno diário: vale para qualquer dia, o que permite adiar cirurgias para outra data
def test_turno_vale_para_qualquer_dia():
    turno = Turno(time(7), time(19))
    amanha = intervalo("08:00", "09:00").deslocado(24 * 60)
    assert turno.cobre(amanha)
    assert not turno.cobre(intervalo("18:00", "19:30"))


def test_turno_nao_cobre_cirurgia_que_atravessa_a_meia_noite():
    noite = Intervalo(hora("23:00"), hora("23:00") + timedelta(hours=2))
    assert not Turno(time(0), time(23, 59)).cobre(noite)
