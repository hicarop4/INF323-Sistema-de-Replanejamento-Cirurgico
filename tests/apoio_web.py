"""Dados e funções compartilhados pelos testes das telas."""

from datetime import date, datetime, time

DIA = date(2026, 10, 11)
AGORA = datetime(2026, 10, 11, 11, 30)


def as_11_30(dia: date) -> datetime:
    """Relógio fixo dos testes: às 11:30 a manhã do dia já foi feita."""
    return datetime.combine(dia, time(11, 30))


JSON = {"Accept": "application/json"}
AUSENCIA_DO_ANESTESISTA = {
    "tipo": "AUSENCIA_PROFISSIONAL",
    "recurso": "paulo",
    "inicio": "2026-10-11T11:30",
    "fim": "2026-10-11T13:30",
    "acao": "adiar",
    "descricao": "Atestado médico",
}
APLICAR_PRIMEIRA_OPCAO = {
    "opcao": "0",
    "justificativa": "Dra. Lúcia livre",
    "confirmado": "1",
    "acao": "aplicar",
}


def texto(resposta) -> str:
    return resposta.get_data(as_text=True)
