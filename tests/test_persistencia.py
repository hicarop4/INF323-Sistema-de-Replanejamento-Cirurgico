"""Persistência em SQLite: programação do dia e registro de auditoria imutável."""

import sqlite3
from datetime import timedelta

import pytest

from ccreplan.dados_exemplo import cadastros_de_exemplo, centro_de_exemplo
from ccreplan.dominio.tempo import Intervalo
from ccreplan.persistencia import BancoDeDados
from ccreplan.replanejamento.decisao import PedidoDeDecisao, decidir
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia, analisar
from ccreplan.replanejamento.opcoes import gerar_opcoes
from ccreplan.web.app import create_app
from tests.apoio_web import (
    APLICAR_PRIMEIRA_OPCAO,
    AUSENCIA_DO_ANESTESISTA,
    DIA,
    as_11_30,
    texto,
)


@pytest.fixture
def banco(tmp_path):
    return BancoDeDados(tmp_path / "ccreplan.sqlite3")


def decisao_tomada(banco, indice=0):
    centro = centro_de_exemplo(DIA)
    inicio = as_11_30(DIA)
    ausencia = Ocorrencia(
        TipoOcorrencia.AUSENCIA_PROFISSIONAL,
        "paulo",
        Intervalo(inicio, inicio + timedelta(hours=2)),
        "Atestado",
    )
    analise = analisar(ausencia, centro)
    opcoes = gerar_opcoes(analise)
    pedido = PedidoDeDecisao("Ana Souza", "Dra. Lúcia livre", inicio, confirmado=True)
    return decidir(analise, opcoes, indice, pedido, banco), opcoes


def test_banco_novo_nao_tem_programacao(banco):
    assert banco.carregar_programacao(cadastros_de_exemplo()) is None


def test_programacao_salva_e_carregada_sem_perder_nada(banco):
    centro, _ = decisao_tomada(banco)
    banco.salvar_programacao(centro)
    carregado = banco.carregar_programacao(cadastros_de_exemplo())
    assert set(carregado.cirurgias) == set(centro.cirurgias)
    assert carregado.indisponibilidades == centro.indisponibilidades


def test_decisao_fica_registrada_no_banco(banco):
    _, opcoes = decisao_tomada(banco)
    (registro,) = banco.decisoes()
    assert registro.ocorrencia.tipo is TipoOcorrencia.AUSENCIA_PROFISSIONAL
    assert registro.ocorrencia.descricao == "Atestado"
    assert registro.opcao_adotada == opcoes[0].descricao
    assert registro.opcoes == tuple(o.descricao for o in opcoes)
    assert (registro.responsavel, registro.justificativa) == ("Ana Souza", "Dra. Lúcia livre")
    assert registro.momento == as_11_30(DIA)
    assert not registro.rejeitada


def test_decisao_rejeitada_fica_sem_opcao_adotada(banco):
    decisao_tomada(banco, indice=None)
    assert banco.decisoes()[0].rejeitada


@pytest.mark.parametrize(
    "comando", ["UPDATE decisoes SET justificativa = 'outra'", "DELETE FROM decisoes"]
)
def test_banco_nao_deixa_alterar_nem_excluir_decisoes(banco, tmp_path, comando):
    decisao_tomada(banco)
    with (
        pytest.raises(sqlite3.DatabaseError),
        sqlite3.connect(tmp_path / "ccreplan.sqlite3") as con,
    ):
        con.execute(comando)
    assert len(banco.decisoes()) == 1


def test_dados_continuam_depois_de_reiniciar_a_aplicacao(banco):
    def nova_aplicacao():
        return create_app(banco=banco, relogio=lambda: as_11_30(DIA)).test_client()

    cliente = nova_aplicacao()
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    cliente.post("/decisao", data=APLICAR_PRIMEIRA_OPCAO)

    pagina = texto(nova_aplicacao().get("/"))
    assert "Dra. Lúcia livre" in pagina  # auditoria
    assert banco.carregar_programacao(cadastros_de_exemplo()).indisponibilidades


def test_em_um_novo_dia_monta_a_programacao_de_hoje_e_mantem_a_auditoria(banco):
    create_app(banco=banco, relogio=lambda: as_11_30(DIA))
    decisao_tomada(banco)
    amanha = DIA + timedelta(days=1)
    pagina = texto(create_app(banco=banco, relogio=lambda: as_11_30(amanha)).test_client().get("/"))
    assert "Hoje · 12/10/2026" in pagina
    assert "13:00–15:00 Artroplastia" in pagina
    assert "Dra. Lúcia livre" in pagina


def test_situacoes_atualizadas_pelo_horario_ficam_salvas(banco):
    create_app(banco=banco, relogio=lambda: as_11_30(DIA)).test_client().get("/")
    salva = banco.carregar_programacao(cadastros_de_exemplo())
    assert salva.cirurgia("c1").situacao.value == "concluída"
    assert salva.cirurgia("c4").situacao.value == "em andamento"


def test_horario_original_da_adiada_e_salvo(banco):
    centro = centro_de_exemplo(DIA)
    c6 = centro.cirurgia("c6")
    adiada = c6.remarcada(c6.horario.deslocado(24 * 60))
    banco.salvar_programacao(centro.com_cirurgia(adiada).com_adiamento("c6", c6.horario))
    assert banco.carregar_programacao(cadastros_de_exemplo()).horario_original("c6") == c6.horario


def test_banco_antigo_sem_a_tabela_de_adiamentos_continua_funcionando(tmp_path):
    caminho = tmp_path / "antigo.sqlite3"
    with sqlite3.connect(caminho) as con:
        con.execute(
            "CREATE TABLE cirurgias (id TEXT PRIMARY KEY, paciente_id TEXT, procedimento_id TEXT,"
            " sala_id TEXT, inicio TEXT, fim TEXT, equipe TEXT, situacao TEXT)"
        )
    con.close()
    banco = BancoDeDados(caminho)
    banco.salvar_programacao(centro_de_exemplo(DIA))
    assert banco.carregar_programacao(cadastros_de_exemplo()).horario_original("c6") is None
