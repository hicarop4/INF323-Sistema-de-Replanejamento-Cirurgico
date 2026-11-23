"""Telas do módulo sobre os dados simulados da Clínica São Lucas."""

from datetime import date, datetime, time, timedelta

from ccreplan.dados_exemplo import centro_de_exemplo
from ccreplan.dominio.regras import Validador
from ccreplan.persistencia import BancoDeDados
from ccreplan.web.app import create_app
from tests.apoio_web import APLICAR_PRIMEIRA_OPCAO, AUSENCIA_DO_ANESTESISTA, DIA, texto


def test_dados_de_exemplo_sao_do_plano_basico_e_comecam_validos():
    centro = centro_de_exemplo()
    assert len(centro.cadastros.salas) == 3
    assert all(Validador().e_valida(c, centro) for c in centro.agendadas())


def test_inicio_mostra_a_programacao_do_dia_por_sala(cliente):
    pagina = texto(cliente.get("/"))
    for esperado in ("Sala 01", "Sala 02", "Sala 03", "Artroplastia", "Registrar ocorrência"):
        assert esperado in pagina


def test_registrar_ocorrencia_mostra_as_opcoes_ordenadas(cliente):
    resposta = cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA, follow_redirects=True)
    pagina = texto(resposta)
    assert "Opções de replanejamento" in pagina
    assert "Opção A" in pagina
    assert "Substituir profissional" in pagina
    assert "Tempo de sala perdido" in pagina


def test_ocorrencia_sem_cirurgias_afetadas(cliente):
    dados = {**AUSENCIA_DO_ANESTESISTA, "recurso": "sergio"}
    pagina = texto(cliente.post("/ocorrencias", data=dados, follow_redirects=True))
    assert "Nenhuma cirurgia afetada" in pagina


def test_opcoes_sem_ocorrencia_pendente_volta_ao_inicio(cliente):
    assert cliente.get("/opcoes").headers["Location"] == "/"


def test_aplicar_sem_justificativa_nao_registra(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = {"opcao": "0", "justificativa": "", "confirmado": "1", "acao": "aplicar"}
    pagina = texto(cliente.post("/decisao", data=dados, follow_redirects=True))
    assert "Informe uma justificativa" in pagina
    assert "Nenhuma decisão registrada" in texto(cliente.get("/"))


def test_aplicar_sem_confirmacao_nao_registra(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = {"opcao": "0", "justificativa": "Dra. Lúcia livre", "acao": "aplicar"}
    pagina = texto(cliente.post("/decisao", data=dados, follow_redirects=True))
    assert "confirmação" in pagina


def test_aplicar_opcao_atualiza_e_registra_para_auditoria(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = APLICAR_PRIMEIRA_OPCAO
    pagina = texto(cliente.post("/decisao", data=dados, follow_redirects=True))
    assert "Programação atualizada. Decisão registrada para auditoria." in pagina
    assert "Ana Souza" in pagina
    assert "Dra. Lúcia livre" in pagina


def test_rejeitar_todas_registra_como_rejeitadas(cliente):
    cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA)
    dados = {"justificativa": "Aguardar retorno", "confirmado": "1", "acao": "rejeitar"}
    pagina = texto(cliente.post("/decisao", data=dados, follow_redirects=True))
    assert "Rejeitadas" in pagina


def test_recursos_mostram_a_especialidade_do_cirurgiao(cliente):
    pagina = texto(cliente.get("/"))
    assert "Dr. Carlos Lima (cirurgião · ortopedia)" in pagina
    assert "Dr. Rafael Costa (cirurgião · ginecologia e obstetrícia)" in pagina


def test_hover_da_programacao_mostra_paciente_e_equipe(cliente):
    pagina = texto(cliente.get("/"))
    detalhe = pagina.split("13:00–15:00")[0].rsplit("title=", 1)[1]
    assert "Luiza Martins" in detalhe
    assert "Dr. Carlos Lima (cirurgião · ortopedia)" in detalhe
    assert "Pedro Nunes (instrumentador)" in detalhe


def test_periodo_afetado_pode_durar_dias_ou_meses(cliente):
    licenca = {**AUSENCIA_DO_ANESTESISTA, "fim": "2026-11-15T18:00", "descricao": "Licença"}
    pagina = texto(cliente.post("/ocorrencias", data=licenca, follow_redirects=True))
    assert "Período: 11/10/2026 11:30 a 15/11/2026 18:00" in pagina
    assert "Substituir profissional" in pagina


def test_por_padrao_a_programacao_e_o_periodo_sao_de_hoje(tmp_path, monkeypatch):
    monkeypatch.setenv("CCREPLAN_BANCO", str(tmp_path / "padrao.sqlite3"))
    hoje = date.today()
    pagina = texto(create_app().test_client().get("/"))
    assert f'name="inicio" type="datetime-local" value="{hoje.isoformat()}T' in pagina
    assert f"Hoje · {hoje.strftime('%d/%m/%Y')}" in pagina


def test_programacao_de_exemplo_e_montada_no_dia_pedido():
    centro = centro_de_exemplo(DIA)
    tres_dias = {DIA, DIA + timedelta(days=1), DIA + timedelta(days=2)}
    assert {c.horario.inicio.date() for c in centro.cirurgias} == tres_dias


def test_opcao_de_adiar_mostra_para_qual_dia(cliente):
    pagina = texto(
        cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA, follow_redirects=True)
    )
    # 12/10 e 13/10 já têm cirurgias na Sala 02 nesse horário; o primeiro dia livre é 14/10
    assert "Artroplastia L.M.: 13:00 Sala 02 → 14/10 13:00 Sala 02" in pagina


def test_programacao_mostra_os_proximos_3_dias(cliente):
    pagina = texto(cliente.get("/"))
    for titulo in ("Hoje · 11/10/2026", "Amanhã · 12/10/2026", "Depois de amanhã · 13/10/2026"):
        assert titulo in pagina
    amanha = pagina.split("Amanhã · 12/10/2026")[1].split("Depois de amanhã")[0]
    assert "08:00–10:00 Artroplastia" in amanha


def test_replanejamento_funciona_para_cirurgias_de_outro_dia(cliente):
    sala_amanha = {
        **AUSENCIA_DO_ANESTESISTA,
        "tipo": "SALA_INDISPONIVEL",
        "recurso": "S2",
        "inicio": "2026-10-12T07:00",
        "fim": "2026-10-12T12:00",
    }
    pagina = texto(cliente.post("/ocorrencias", data=sala_amanha, follow_redirects=True))
    assert "Opções de replanejamento" in pagina
    assert "12/10 08:00 Sala 02 Artroplastia" in pagina


def test_situacao_das_cirurgias_segue_o_relogio(tmp_path):
    def programacao_as(hhmm):
        relogio = datetime.combine(DIA, time.fromisoformat(hhmm))
        banco = BancoDeDados(tmp_path / f"{hhmm.replace(':', '')}.sqlite3")
        app = create_app(centro_de_exemplo(DIA), relogio=lambda: relogio, banco=banco)
        return " ".join(texto(app.test_client().get("/")).split("Amanhã")[0].split())

    herniorrafia = '11:00–12:00 Herniorrafia P.F.O. <span class="situacao">'
    assert herniorrafia + "(agendada)" in programacao_as("08:00")
    assert herniorrafia + "(em andamento)" in programacao_as("11:30")
    assert herniorrafia + "(concluída)" in programacao_as("13:00")
