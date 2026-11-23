"""Gerar opções de replanejamento ordenadas pelo impacto."""

from dataclasses import dataclass
from datetime import time
from typing import Protocol

from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.dominio.modelos import Cirurgia, Situacao
from ccreplan.dominio.regras import Validador
from ccreplan.replanejamento.ocorrencias import Analise

PASSO_MIN = 10
FIM_DO_EXPEDIENTE = time(19, 0)
MINUTOS_NO_DIA = 24 * 60
DIAS_PARA_PROCURAR = 60


@dataclass(frozen=True)
class Movimento:
    original: Cirurgia
    nova: Cirurgia

    @property
    def tempo_perdido_min(self) -> int:
        """Minutos de sala perdidos hoje: o atraso, ou a duração se a cirurgia sai do dia."""
        saiu_do_dia = self.nova.horario.inicio.date() != self.original.horario.inicio.date()
        if saiu_do_dia or not self.nova.ocupa_recursos:
            return self.original.horario.duracao_min
        atraso = self.nova.horario.inicio - self.original.horario.inicio
        return max(0, int(atraso.total_seconds() // 60))

    @property
    def adia(self) -> bool:
        return self.nova.ocupa_recursos and self.nova.horario.inicio > self.original.horario.inicio

    @property
    def afeta_paciente(self) -> bool:
        antes, depois = self.original, self.nova
        return (antes.horario, antes.sala_id, antes.situacao) != (
            depois.horario,
            depois.sala_id,
            depois.situacao,
        )


@dataclass(frozen=True)
class Impacto:
    tempo_sala_perdido_min: int
    pacientes_afetados: int
    restricoes_no_limite: tuple[str, ...]

    def chave(self) -> tuple[int, int, int]:
        return (
            self.tempo_sala_perdido_min,
            self.pacientes_afetados,
            len(self.restricoes_no_limite),
        )


@dataclass(frozen=True)
class Opcao:
    descricao: str
    movimentos: tuple[Movimento, ...]
    impacto: Impacto

    def aplicar_em(self, centro: CentroCirurgico) -> CentroCirurgico:
        for movimento in self.movimentos:
            centro = centro.com_cirurgia(movimento.nova)
            if movimento.adia:
                centro = centro.com_adiamento(movimento.original.id, movimento.original.horario)
        return centro


class Estrategia(Protocol):
    def propor(self, cirurgia: Cirurgia, centro: CentroCirurgico, validador: Validador):
        """Devolve a cirurgia remarcada, ou None se a estratégia não resolve."""


def _primeira_valida(candidatas, centro: CentroCirurgico, validador: Validador):
    return next((c for c in candidatas if validador.e_valida(c, centro.com_cirurgia(c))), None)


class SubstituirProfissional:
    def propor(self, cirurgia, centro, validador):
        profissionais = centro.cadastros.profissionais
        candidatas = (
            cirurgia.com_equipe(cirurgia.equipe - {saindo.id} | {entrando.id})
            for saindo in map(centro.cadastros.profissional, sorted(cirurgia.equipe))
            for entrando in profissionais
            if saindo.pode_ser_substituido_por(entrando) and entrando.id not in cirurgia.equipe
        )
        return _primeira_valida(candidatas, centro, validador)


class MudarDeSala:
    def propor(self, cirurgia, centro, validador):
        candidatas = (
            cirurgia.remarcada(sala_id=sala.id)
            for sala in centro.cadastros.salas
            if sala.id != cirurgia.sala_id
        )
        return _primeira_valida(candidatas, centro, validador)


class AdiarNoDia:
    def propor(self, cirurgia, centro, validador):
        limite = cirurgia.horario.inicio.replace(
            hour=FIM_DO_EXPEDIENTE.hour, minute=FIM_DO_EXPEDIENTE.minute
        )
        candidatas = []
        horario = cirurgia.horario.deslocado(PASSO_MIN)
        while horario.fim <= limite:
            candidatas.append(cirurgia.remarcada(horario))
            horario = horario.deslocado(PASSO_MIN)
        return _primeira_valida(candidatas, centro, validador)


class AdiarParaOutroDia:
    """Primeiro dia seguinte em que a cirurgia cabe no mesmo horário e na mesma sala."""

    def propor(self, cirurgia, centro, validador):
        candidatas = (
            cirurgia.remarcada(cirurgia.horario.deslocado(dias * MINUTOS_NO_DIA))
            for dias in range(1, DIAS_PARA_PROCURAR + 1)
        )
        return _primeira_valida(candidatas, centro, validador)


class MudarSituacao:
    def __init__(self, situacao: Situacao):
        self._situacao = situacao

    def propor(self, cirurgia, centro, validador):
        return cirurgia.com_situacao(self._situacao)


@dataclass(frozen=True)
class Plano:
    """Aplica as estratégias, na ordem, a cada cirurgia afetada."""

    descricao: str
    estrategias: tuple[Estrategia, ...]

    def gerar(self, analise: Analise, validador: Validador) -> Opcao | None:
        centro, movimentos = analise.centro, []
        for afetada in analise.afetadas:
            nova = self._propor(afetada, centro, validador)
            if nova is None:
                return None
            centro = centro.com_cirurgia(nova)
            movimentos.append(Movimento(afetada, nova))
        if not self._tudo_valido(analise, centro, validador):
            return None
        return Opcao(self.descricao, tuple(movimentos), _impacto(movimentos, centro, validador))

    def _propor(self, cirurgia, centro, validador):
        propostas = (e.propor(cirurgia, centro, validador) for e in self.estrategias)
        return next((p for p in propostas if p is not None), None)

    @staticmethod
    def _tudo_valido(analise: Analise, depois: CentroCirurgico, validador: Validador) -> bool:
        afetadas = {c.id for c in analise.afetadas}
        return all(
            validador.e_valida(c, depois)
            for c in depois.agendadas()
            if c.id in afetadas or validador.e_valida(analise.centro.cirurgia(c.id), analise.centro)
        )


def _impacto(movimentos, centro, validador) -> Impacto:
    limites = [
        limite
        for m in movimentos
        if m.nova.ocupa_recursos
        for limite in validador.verificar(m.nova, centro).limites
    ]
    return Impacto(
        tempo_sala_perdido_min=sum(m.tempo_perdido_min for m in movimentos),
        pacientes_afetados=sum(m.afeta_paciente for m in movimentos),
        restricoes_no_limite=tuple(dict.fromkeys(limites)),
    )


PLANOS_PADRAO = (
    Plano("Substituir profissional", (SubstituirProfissional(),)),
    Plano("Realocar em outra sala", (MudarDeSala(),)),
    Plano("Adiar no mesmo dia", (AdiarNoDia(),)),
    Plano(
        "Realocar ou adiar no mesmo dia", (SubstituirProfissional(), MudarDeSala(), AdiarNoDia())
    ),
    Plano("Adiar para outro dia", (AdiarParaOutroDia(),)),
)
PLANOS_CANCELAMENTO = (Plano("Cancelar cirurgias afetadas", (MudarSituacao(Situacao.CANCELADA),)),)


def gerar_opcoes(
    analise: Analise, validador: Validador | None = None, planos: tuple[Plano, ...] = PLANOS_PADRAO
) -> list[Opcao]:
    if not analise.afetadas:
        return []
    validador = validador or Validador()
    unicas = {}
    for plano in planos:
        opcao = plano.gerar(analise, validador)
        if opcao is not None:
            unicas.setdefault(opcao.movimentos, opcao)
    return sorted(unicas.values(), key=lambda o: o.impacto.chave())
