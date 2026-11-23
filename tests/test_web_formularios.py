"""Formulários: validação, envio sem recarregar a página e recursos filtrados pelo tipo."""

import json

import pytest

from ccreplan.dados_exemplo import centro_de_exemplo
from ccreplan.replanejamento.ocorrencias import TipoOcorrencia
from ccreplan.web.apresentacao import recursos_por_tipo
from tests.apoio_web import AGORA, APLICAR_PRIMEIRA_OPCAO, AUSENCIA_DO_ANESTESISTA, DIA, JSON, texto


@pytest.mark.parametrize(
    "periodo",
    [
        {"inicio": ""},
        {"fim": "abc"},
        {"fim": "13:30"},
        {"inicio": "2026-10-12T08:00", "fim": "2026-10-11T13:30"},
    ],
)
def test_formulario_incompleto_avisa_o_funcionario(cliente, periodo):
    dados = {**AUSENCIA_DO_ANESTESISTA, **periodo}
    pagina = texto(cliente.post("/ocorrencias", data=dados, follow_redirects=True))
    assert "Preencha o tipo, o recurso e o período afetado" in pagina


def test_periodo_afetado_em_inicio_e_fim_e_descricao_opcional(cliente):
    pagina = texto(cliente.get("/"))
    assert 'name="inicio" type="datetime-local" value="2026-10-11T11:30"' in pagina
    assert 'name="fim" type="datetime-local" value="2026-10-11T13:30"' in pagina
    assert "Descrição (opcional)" in pagina


def test_formularios_sao_enviados_sem_recarregar_a_pagina(cliente):
    assert 'action="/ocorrencias" data-envio-sem-recarregar' in texto(cliente.get("/"))
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    assert 'action="/decisao" data-envio-sem-recarregar' in texto(cliente.get("/opcoes"))


def test_ocorrencia_invalida_responde_aviso_sem_trocar_de_pagina(cliente):
    resposta = cliente.post(
        "/ocorrencias", data={**AUSENCIA_DO_ANESTESISTA, "fim": ""}, headers=JSON
    )
    assert resposta.status_code == 400
    assert "período afetado" in resposta.get_json()["mensagem"]


def test_ocorrencia_sem_afetadas_responde_aviso(cliente):
    dados = {**AUSENCIA_DO_ANESTESISTA, "recurso": "sergio"}
    resposta = cliente.post("/ocorrencias", data=dados, headers=JSON)
    assert resposta.get_json() == {"mensagem": "Nenhuma cirurgia afetada pela ocorrência."}


def test_ocorrencia_valida_indica_a_tela_de_opcoes(cliente):
    resposta = cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA, headers=JSON)
    assert resposta.get_json() == {"proxima": "/opcoes"}


def test_decisao_sem_justificativa_responde_aviso_e_mantem_a_tela(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = {"opcao": "0", "justificativa": "", "confirmado": "1", "acao": "aplicar"}
    resposta = cliente.post("/decisao", data=dados, headers=JSON)
    assert resposta.status_code == 400
    assert "justificativa" in resposta.get_json()["mensagem"]


def test_decisao_aplicada_indica_o_inicio_com_a_confirmacao(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = APLICAR_PRIMEIRA_OPCAO
    assert cliente.post("/decisao", data=dados, headers=JSON).get_json() == {"proxima": "/"}
    assert "Decisão registrada para auditoria" in texto(cliente.get("/"))


def test_recursos_agrupados_pelo_tipo_de_ocorrencia():
    recursos = recursos_por_tipo(centro_de_exemplo())
    assert set(recursos) == {tipo.name for tipo in TipoOcorrencia}
    assert recursos["SALA_INDISPONIVEL"] == [
        ("S1", "Sala 01"),
        ("S2", "Sala 02"),
        ("S3", "Sala 03"),
    ]
    assert all(
        rid in {"pinca", "afastador", "porta-agulha"}
        for rid, _ in recursos["INSTRUMENTO_INDISPONIVEL"]
    )
    assert "paulo" in dict(recursos["AUSENCIA_PROFISSIONAL"])
    assert "L.M." in dict(recursos["PACIENTE_INDISPONIVEL"])


def test_atraso_lista_so_cirurgias_agendadas_ou_em_andamento():
    centro = centro_de_exemplo(DIA).com_situacoes_em(AGORA)
    cirurgias = dict(recursos_por_tipo(centro)["ATRASO_CIRURGIA"])
    assert "c4" in cirurgias  # em andamento
    assert "c6" in cirurgias  # agendada
    assert "c1" not in cirurgias  # concluída
    assert cirurgias["c6"] == "11/10 13:00 Sala 02 · Artroplastia L.M."


def test_tela_recebe_os_recursos_de_cada_tipo_para_filtrar_a_lista(cliente):
    pagina = texto(cliente.get("/"))
    bloco = pagina.split('<script type="application/json" id="recursos-por-tipo">')[1]
    recursos = json.loads(bloco.split("</script>")[0])
    assert ["S1", "Sala 01"] in recursos["SALA_INDISPONIVEL"]


@pytest.mark.parametrize(
    ("tipo", "recurso"),
    [("SALA_INDISPONIVEL", "paulo"), ("ATRASO_CIRURGIA", "paulo"), ("ATRASO_CIRURGIA", "c1")],
)
def test_recurso_que_nao_combina_com_o_tipo_e_recusado(cliente, tipo, recurso):
    dados = {**AUSENCIA_DO_ANESTESISTA, "tipo": tipo, "recurso": recurso}
    resposta = cliente.post("/ocorrencias", data=dados, headers=JSON)
    assert resposta.status_code == 400
    assert resposta.get_json() == {
        "mensagem": "O recurso escolhido não corresponde ao tipo de ocorrência."
    }
