"""Programação: cirurgias canceladas e o horário original das adiadas aparecem riscados."""

from ccreplan.dados_exemplo import centro_de_exemplo
from ccreplan.web.apresentacao import linhas_da_programacao
from tests.apoio_web import APLICAR_PRIMEIRA_OPCAO, AUSENCIA_DO_ANESTESISTA, DIA, texto


def aplicar(cliente, descricao, ocorrencia=AUSENCIA_DO_ANESTESISTA):
    cliente.post("/ocorrencias", data=ocorrencia)
    opcoes = cliente.application.extensions["clinica"].pendente[1]
    indice = next(i for i, o in enumerate(opcoes) if o.descricao == descricao)
    dados = {**APLICAR_PRIMEIRA_OPCAO, "opcao": str(indice)}
    return texto(cliente.post("/decisao", data=dados, follow_redirects=True))


def secao(pagina, inicio, fim):
    return " ".join(pagina.split(inicio)[1].split(fim)[0].split())


def linha_de(secao_do_dia, rotulo):
    antes, depois = secao_do_dia.split(rotulo, 1)
    return antes.rsplit("<div", 1)[1] + rotulo + depois.split("</div>", 1)[0]


def test_cirurgia_cancelada_aparece_riscada(cliente):
    cancelar = {**AUSENCIA_DO_ANESTESISTA, "acao": "cancelar"}
    pagina = aplicar(cliente, "Cancelar cirurgias afetadas", cancelar)
    hoje = secao(pagina, "Hoje · 11/10/2026", "Amanhã")
    assert 'class="riscada"' in linha_de(hoje, "Artroplastia L.M.")
    assert hoje.count('class="riscada"') == 1


def test_adiada_para_outro_dia_fica_riscada_no_horario_original(cliente):
    pagina = aplicar(cliente, "Adiar para outro dia")
    hoje = secao(pagina, "Hoje · 11/10/2026", "Amanhã")
    original = linha_de(hoje, "Artroplastia L.M.")
    assert 'class="riscada"' in original
    assert "13:00–15:00" in original
    assert "(adiada para 14/10 13:00)" in original


def test_adiada_no_mesmo_dia_mostra_o_original_riscado_e_o_novo_horario():
    centro = centro_de_exemplo(DIA)
    c6 = centro.cirurgia("c6")
    adiado = centro.com_cirurgia(c6.remarcada(c6.horario.deslocado(180)))
    linhas = linhas_da_programacao(adiado.com_adiamento("c6", c6.horario), "S2", DIA)
    artroplastia = [linha for linha in linhas if linha.cirurgia.id == "c6"]
    assert [(linha.horario, linha.riscada) for linha in artroplastia] == [
        ("13:00–15:00", True),
        ("16:00–18:00", False),
    ]
    assert artroplastia[0].situacao == "adiada para 16:00"


def test_mudar_so_de_sala_nao_deixa_horario_riscado(cliente):
    atraso = {
        **AUSENCIA_DO_ANESTESISTA,
        "tipo": "ATRASO_CIRURGIA",
        "recurso": "c5",
        "inicio": "2026-10-11T12:50",
        "fim": "2026-10-11T13:30",
    }
    pagina = aplicar(cliente, "Realocar em outra sala", atraso)
    assert 'class="riscada"' not in secao(pagina, "Hoje · 11/10/2026", "Amanhã")
