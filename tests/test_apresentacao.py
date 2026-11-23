"""Textos mostrados nas telas."""

import pytest

from ccreplan.web.apresentacao import duracao
from tests.apoio_web import AUSENCIA_DO_ANESTESISTA, texto


@pytest.mark.parametrize(
    ("minutos", "esperado"),
    [
        (0, "0 min"),
        (45, "45 min"),
        (60, "1 h"),
        (90, "1 h 30 min"),
        (930, "15 h 30 min"),
        (1440, "1 dia"),
        (1470, "1 dia 30 min"),
        (1500, "1 dia 1 h"),
        (3000, "2 dias 2 h"),
        (3031, "2 dias 2 h 31 min"),
    ],
)
def test_duracao_em_dias_horas_e_minutos_sem_unidades_zeradas(minutos, esperado):
    assert duracao(minutos) == esperado


def test_tempo_de_sala_perdido_aparece_em_horas_e_minutos(cliente):
    resposta = cliente.post("/ocorrencias", data=AUSENCIA_DO_ANESTESISTA, follow_redirects=True)
    pagina = texto(resposta)
    substituir, adiar_120_min = "<strong>0 min</strong>", "<strong>2 h</strong>"
    assert f"Tempo de sala perdido: {substituir}" in pagina
    assert f"Tempo de sala perdido: {adiar_120_min}" in pagina
