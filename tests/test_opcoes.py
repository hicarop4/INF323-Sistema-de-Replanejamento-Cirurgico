"""Gerar opções de replanejamento."""

from dataclasses import replace
from datetime import timedelta

from ccreplan.dominio.modelos import Situacao
from ccreplan.dominio.regras import Validador
from ccreplan.dominio.tempo import Intervalo
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia, analisar
from ccreplan.replanejamento.opcoes import PLANOS_CANCELAMENTO, Plano, gerar_opcoes
from tests.construtor import Cenario, hora, intervalo

OUTRA_EQUIPE = ("cir2", "anest2", "enf2")
DIA_TODO = intervalo("07:00", "19:00")


def analise_de_atraso():
    """A cirurgia anterior atrasa e a seguinte precisa mudar."""
    cenario = Cenario().com_cirurgia("c1", "08:00").com_cirurgia("c2", "09:30", equipe=OUTRA_EQUIPE)
    atraso = Ocorrencia(TipoOcorrencia.ATRASO_CIRURGIA, "c1", intervalo("09:00", "09:20"))
    return analisar(atraso, cenario.construir())


def por_descricao(opcoes, descricao):
    return next(opcao for opcao in opcoes if opcao.descricao == descricao)


def test_opcoes_ordenadas_do_menor_para_o_maior_impacto():
    opcoes = gerar_opcoes(analise_de_atraso())
    assert [o.descricao for o in opcoes] == [
        "Realocar em outra sala",
        "Adiar no mesmo dia",
        "Adiar para outro dia",
    ]
    assert [o.impacto.tempo_sala_perdido_min for o in opcoes] == [0, 20, 60]


def test_adiar_no_mesmo_dia_respeita_a_higienizacao_e_mostra_a_restricao_no_limite():
    adiar = por_descricao(gerar_opcoes(analise_de_atraso()), "Adiar no mesmo dia")
    (movimento,) = adiar.movimentos
    assert movimento.nova.horario == intervalo("09:50", "10:50")
    assert movimento.nova.sala_id == "S1"
    assert adiar.impacto.pacientes_afetados == 1
    assert "limpeza da Sala 01" in adiar.impacto.restricoes_no_limite


def test_todas_as_opcoes_geradas_sao_validas():
    analise = analise_de_atraso()
    validador = Validador()
    for opcao in gerar_opcoes(analise):
        depois = opcao.aplicar_em(analise.centro)
        assert all(validador.e_valida(c, depois) for c in depois.agendadas()), opcao.descricao


def test_opcoes_repetidas_aparecem_uma_vez_so():
    opcoes = gerar_opcoes(analise_de_atraso())
    assert len({o.movimentos for o in opcoes}) == len(opcoes)


def test_substituir_profissional_e_a_opcao_de_menor_impacto_na_ausencia():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    ausencia = Ocorrencia(
        TipoOcorrencia.AUSENCIA_PROFISSIONAL, "anest1", intervalo("07:00", "12:00")
    )
    melhor = gerar_opcoes(analisar(ausencia, cenario.construir()))[0]
    assert melhor.descricao == "Substituir profissional"
    assert melhor.impacto.tempo_sala_perdido_min == 0
    assert melhor.impacto.pacientes_afetados == 0
    assert melhor.movimentos[0].nova.equipe == {"cir1", "anest2", "enf1"}


def test_pacientes_afetados_conta_cada_cirurgia_remarcada():
    cenario = Cenario().com_cirurgia("c1", "08:00").com_cirurgia("c2", "10:00")
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S1", DIA_TODO)
    realocar = por_descricao(
        gerar_opcoes(analisar(sala, cenario.construir())), "Realocar em outra sala"
    )
    assert realocar.impacto.pacientes_afetados == 2
    assert {m.nova.sala_id for m in realocar.movimentos} == {"S2"}


def test_plano_que_nao_consegue_realocar_todas_as_cirurgias_e_descartado():
    cenario = Cenario()
    procedimento = cenario.procedimentos["colecistectomia"]
    cenario.com_procedimento(replace(procedimento, salas_permitidas=frozenset({"S1", "S2"})))
    cenario.com_cirurgia("c1", "08:00").com_cirurgia("c2", "08:00", sala="S2", equipe=OUTRA_EQUIPE)
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S1", DIA_TODO)
    opcoes = gerar_opcoes(analisar(sala, cenario.construir()))
    assert [o.descricao for o in opcoes] == ["Adiar para outro dia"]


def test_adiar_para_outro_dia_sugere_o_dia_seguinte_no_mesmo_horario_e_sala():
    adiar = por_descricao(gerar_opcoes(analise_de_atraso()), "Adiar para outro dia")
    nova = adiar.movimentos[0].nova
    assert nova.horario == intervalo("09:30", "10:30").deslocado(24 * 60)
    assert nova.sala_id == "S1"
    assert nova.situacao is Situacao.AGENDADA
    assert adiar.impacto.tempo_sala_perdido_min == 60  # o que se perde é o horário de hoje


def test_adiar_para_outro_dia_pula_os_dias_em_que_o_recurso_continua_indisponivel():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    tres_dias = Intervalo(hora("07:00"), hora("19:00") + timedelta(days=2))
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S1", tres_dias)
    adiar = por_descricao(gerar_opcoes(analisar(sala, cenario.construir())), "Adiar para outro dia")
    assert adiar.movimentos[0].nova.horario.inicio == hora("08:00") + timedelta(days=3)


def test_acao_cancelar_gera_so_a_opcao_de_cancelamento():
    opcoes = gerar_opcoes(analise_de_atraso(), planos=PLANOS_CANCELAMENTO)
    assert [o.descricao for o in opcoes] == ["Cancelar cirurgias afetadas"]
    assert opcoes[0].movimentos[0].nova.situacao is Situacao.CANCELADA


def test_sem_cirurgias_afetadas_nao_ha_opcoes():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    ausencia = Ocorrencia(TipoOcorrencia.AUSENCIA_PROFISSIONAL, "anest2", DIA_TODO)
    assert gerar_opcoes(analisar(ausencia, cenario.construir())) == []


class MoverParaSalaOcupada:
    """Estratégia falsa que ignora as regras, para provar que o plano não confia nela."""

    def propor(self, cirurgia, centro, validador):
        return cirurgia.remarcada(sala_id="S2")


def test_plano_descarta_proposta_que_quebra_outra_cirurgia():
    cenario = Cenario().com_cirurgia("c1", "08:00")
    cenario.com_cirurgia("c2", "08:00", sala="S2", equipe=OUTRA_EQUIPE)
    sala = Ocorrencia(TipoOcorrencia.SALA_INDISPONIVEL, "S1", DIA_TODO)
    plano = Plano("Teste", (MoverParaSalaOcupada(),))
    assert plano.gerar(analisar(sala, cenario.construir()), Validador()) is None


def test_substituto_precisa_ter_a_mesma_especialidade():
    cenario = (
        Cenario().com_especialidade("cir1", "ortopedia").com_especialidade("cir2", "obstetrícia")
    )
    cenario.com_cirurgia("c1", "08:00")
    ausencia = Ocorrencia(TipoOcorrencia.AUSENCIA_PROFISSIONAL, "cir1", intervalo("07:00", "12:00"))
    opcoes = gerar_opcoes(analisar(ausencia, cenario.construir()))
    assert "Substituir profissional" not in [o.descricao for o in opcoes]


def test_adiar_guarda_o_horario_original_e_mudar_de_sala_nao():
    analise = analise_de_atraso()
    opcoes = gerar_opcoes(analise)

    def original_depois_de(descricao):
        return por_descricao(opcoes, descricao).aplicar_em(analise.centro).horario_original("c2")

    assert original_depois_de("Adiar no mesmo dia") == intervalo("09:30", "10:30")
    assert original_depois_de("Adiar para outro dia") == intervalo("09:30", "10:30")
    assert original_depois_de("Realocar em outra sala") is None
