"""Decidir replanejamento e Registrar decisão para auditoria."""

from dataclasses import FrozenInstanceError

import pytest

from ccreplan.replanejamento.decisao import (
    DecisaoInvalida,
    PedidoDeDecisao,
    RegistroAuditoria,
    decidir,
)
from ccreplan.replanejamento.opcoes import gerar_opcoes
from tests.construtor import hora, intervalo
from tests.test_opcoes import analise_de_atraso


def pedido(justificativa="Sala 02 livre no horário", confirmado=True):
    return PedidoDeDecisao("Ana Souza", justificativa, hora("09:05"), confirmado)


@pytest.fixture
def cenario():
    analise = analise_de_atraso()
    return analise, gerar_opcoes(analise), RegistroAuditoria()


def test_nenhuma_opcao_e_aplicada_sem_confirmacao(cenario):
    analise, opcoes, auditoria = cenario
    with pytest.raises(DecisaoInvalida):
        decidir(analise, opcoes, 0, pedido(confirmado=False), auditoria)
    assert auditoria.decisoes() == ()


@pytest.mark.parametrize("justificativa", ["", "   "])
def test_justificativa_e_obrigatoria(cenario, justificativa):
    analise, opcoes, auditoria = cenario
    with pytest.raises(DecisaoInvalida):
        decidir(analise, opcoes, 0, pedido(justificativa), auditoria)
    assert auditoria.decisoes() == ()


def test_aplicar_opcao_atualiza_a_programacao(cenario):
    analise, opcoes, auditoria = cenario
    adiar = next(i for i, o in enumerate(opcoes) if o.descricao == "Adiar no mesmo dia")
    centro = decidir(analise, opcoes, adiar, pedido(), auditoria)
    assert centro.cirurgia("c2").horario == intervalo("09:50", "10:50")


def test_decisao_registra_tudo_para_auditoria(cenario):
    analise, opcoes, auditoria = cenario
    decidir(analise, opcoes, 0, pedido(), auditoria)
    (decisao,) = auditoria.decisoes()
    assert decisao.ocorrencia == analise.ocorrencia
    assert decisao.opcoes == tuple(opcoes)
    assert decisao.escolhida == opcoes[0]
    assert (decisao.responsavel, decisao.justificativa) == ("Ana Souza", "Sala 02 livre no horário")
    assert decisao.momento == hora("09:05")


def test_rejeitar_todas_registra_a_decisao_e_mantem_a_programacao(cenario):
    analise, opcoes, auditoria = cenario
    centro = decidir(analise, opcoes, None, pedido("Aguardar a equipe"), auditoria)
    assert centro.cirurgia("c2") == analise.centro.cirurgia("c2")
    assert auditoria.decisoes()[0].rejeitada


def test_decisao_registrada_nao_pode_ser_alterada(cenario):
    analise, opcoes, auditoria = cenario
    decidir(analise, opcoes, 0, pedido(), auditoria)
    with pytest.raises(FrozenInstanceError):
        auditoria.decisoes()[0].justificativa = "outra"


def test_registro_de_auditoria_nao_permite_excluir():
    auditoria = RegistroAuditoria()
    assert isinstance(auditoria.decisoes(), tuple)
    assert not any(hasattr(auditoria, nome) for nome in ("remover", "excluir", "alterar", "limpar"))
