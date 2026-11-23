"""Textos mostrados nas telas, para os templates não terem regra nenhuma."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.dominio.modelos import Cirurgia, Funcao, Situacao
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia
from ccreplan.replanejamento.opcoes import Movimento

LETRAS = "ABCDEFGHIJ"


def hhmm(momento: datetime) -> str:
    return momento.strftime("%H:%M")


def data_hora(momento: datetime) -> str:
    return momento.strftime("%d/%m/%Y %H:%M")


def duracao(minutos: int) -> str:
    """Ex.: 45 min, 2 h, 1 h 30 min, 1 dia 30 min, 2 dias 2 h. Unidades zeradas não aparecem."""
    dias, resto = divmod(minutos, 24 * 60)
    horas, mins = divmod(resto, 60)
    partes = [
        f"{dias} dia{'s' if dias > 1 else ''}" if dias else "",
        f"{horas} h" if horas else "",
        f"{mins} min" if mins else "",
    ]
    return " ".join(filter(None, partes)) or "0 min"


def dia_e_hora(momento: datetime) -> str:
    return momento.strftime("%d/%m %H:%M")


def proximos_dias(hoje: date) -> list[tuple[str, date]]:
    rotulos = ("Hoje", "Amanhã", "Depois de amanhã")
    return [(rotulo, hoje + timedelta(days=n)) for n, rotulo in enumerate(rotulos)]


def descrever_profissional(profissional) -> str:
    area = " · ".join(filter(None, (profissional.funcao.value, profissional.especialidade)))
    return f"{profissional.nome} ({area})"


def detalhes_cirurgia(centro: CentroCirurgico, cirurgia) -> str:
    cadastros = centro.cadastros
    ordem = list(Funcao)
    equipe = sorted(
        map(cadastros.profissional, cirurgia.equipe), key=lambda p: ordem.index(p.funcao)
    )
    linhas = [f"Paciente: {cadastros.paciente(cirurgia.paciente_id).nome}", "Equipe:"]
    return "\n".join(linhas + [f"• {descrever_profissional(p)}" for p in equipe])


def recursos_por_tipo(centro: CentroCirurgico) -> dict[str, list[tuple[str, str]]]:
    """Recursos que podem ser escolhidos em cada tipo de ocorrência."""
    cadastros = centro.cadastros
    ativas = sorted(
        (c for c in centro.cirurgias if c.ocupa_recursos), key=lambda c: c.horario.inicio
    )
    return {
        TipoOcorrencia.AUSENCIA_PROFISSIONAL.name: [
            (p.id, descrever_profissional(p)) for p in cadastros.profissionais
        ],
        TipoOcorrencia.SALA_INDISPONIVEL.name: _por_nome(cadastros.salas),
        TipoOcorrencia.INSTRUMENTO_INDISPONIVEL.name: _por_nome(cadastros.instrumentos),
        TipoOcorrencia.PACIENTE_INDISPONIVEL.name: _por_nome(cadastros.pacientes),
        TipoOcorrencia.ATRASO_CIRURGIA.name: [
            (c.id, f"{dia_e_hora(c.horario.inicio)} {cadastros.sala(c.sala_id).nome} · "
                   f"{rotulo_cirurgia(centro, c)}")
            for c in ativas
        ],
    }  # fmt: skip


def _por_nome(itens) -> list[tuple[str, str]]:
    return [(item.id, item.nome) for item in itens]


def recurso_combina_com_o_tipo(ocorrencia: Ocorrencia, centro: CentroCirurgico) -> bool:
    return ocorrencia.recurso_id in dict(recursos_por_tipo(centro)[ocorrencia.tipo.name])


def nome_do_recurso(ocorrencia: Ocorrencia, centro: CentroCirurgico) -> str:
    rotulos = {rid: rotulo for grupo in recursos_por_tipo(centro).values() for rid, rotulo in grupo}
    return rotulos.get(ocorrencia.recurso_id, ocorrencia.recurso_id)


def rotulo_cirurgia(centro: CentroCirurgico, cirurgia) -> str:
    return f"{centro.procedimento_de(cirurgia).nome} {cirurgia.paciente_id}"


def descrever(movimento: Movimento, centro: CentroCirurgico) -> str:
    antes, depois = movimento.original, movimento.nova
    cadastros = centro.cadastros
    if not depois.ocupa_recursos:
        return f"{depois.situacao.value} ({hhmm(antes.horario.inicio)})"
    if antes.equipe != depois.equipe:
        saiu = ", ".join(
            cadastros.profissional(p).nome for p in sorted(antes.equipe - depois.equipe)
        )
        entrou = ", ".join(
            cadastros.profissional(p).nome for p in sorted(depois.equipe - antes.equipe)
        )
        return f"equipe: {saiu} → {entrou}"
    return (
        f"{hhmm(antes.horario.inicio)} {cadastros.sala(antes.sala_id).nome} → "
        f"{_quando(depois.horario.inicio, antes.horario.inicio)} "
        f"{cadastros.sala(depois.sala_id).nome}"
    )


def _quando(momento: datetime, referencia: datetime) -> str:
    """Só o horário se for no mesmo dia da referência; dia e horário se mudou de data."""
    return hhmm(momento) if momento.date() == referencia.date() else dia_e_hora(momento)


def _faixa(intervalo) -> str:
    return f"{hhmm(intervalo.inicio)}–{hhmm(intervalo.fim)}"


@dataclass(frozen=True)
class LinhaDaProgramacao:
    cirurgia: Cirurgia
    inicio: datetime
    horario: str
    situacao: str
    riscada: bool


def linhas_da_programacao(centro: CentroCirurgico, sala_id: str, dia: date) -> list:
    """Cirurgias da sala no dia; canceladas e o horário original das adiadas vêm riscados."""
    linhas = []
    for c in (c for c in centro.cirurgias if c.sala_id == sala_id):
        original = centro.horario_original(c.id)
        if original is not None and original.inicio.date() == dia:
            adiada = f"adiada para {_quando(c.horario.inicio, original.inicio)}"
            linhas.append(LinhaDaProgramacao(c, original.inicio, _faixa(original), adiada, True))
        if c.horario.inicio.date() == dia:
            riscada = c.situacao in (Situacao.CANCELADA, Situacao.ADIADA)
            linha = LinhaDaProgramacao(
                c, c.horario.inicio, _faixa(c.horario), c.situacao.value, riscada
            )
            linhas.append(linha)
    return sorted(linhas, key=lambda linha: linha.inicio)


def registrar_filtros(app) -> None:
    app.add_template_filter(hhmm)
    app.add_template_filter(data_hora)
    app.add_template_filter(dia_e_hora)
    app.add_template_filter(duracao)
    app.add_template_global(descrever)
    app.add_template_global(rotulo_cirurgia)
    app.add_template_global(detalhes_cirurgia)
    app.add_template_global(linhas_da_programacao)
    app.add_template_global(nome_do_recurso)
    app.add_template_global(LETRAS, "LETRAS")
