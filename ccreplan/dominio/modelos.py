from dataclasses import dataclass, replace
from datetime import datetime, time
from enum import Enum

from ccreplan.dominio.tempo import Intervalo


class Funcao(Enum):
    CIRURGIAO = "cirurgião"
    ANESTESISTA = "anestesista"
    ENFERMEIRO = "enfermeiro"
    INSTRUMENTADOR = "instrumentador"


class Situacao(Enum):
    AGENDADA = "agendada"
    EM_ANDAMENTO = "em andamento"
    CONCLUIDA = "concluída"
    ADIADA = "adiada"
    CANCELADA = "cancelada"

    @property
    def ocupa_recursos(self) -> bool:
        return self in (Situacao.AGENDADA, Situacao.EM_ANDAMENTO)


class TipoRecurso(Enum):
    PROFISSIONAL = "profissional"
    SALA = "sala"
    INSTRUMENTO = "instrumento"
    PACIENTE = "paciente"


@dataclass(frozen=True)
class Sala:
    id: str
    nome: str


@dataclass(frozen=True)
class Paciente:
    id: str
    nome: str


@dataclass(frozen=True)
class Instrumento:
    id: str
    nome: str
    quantidade: int


@dataclass(frozen=True)
class Turno:
    """Horário de trabalho diário: vale para qualquer dia."""

    inicio: time
    fim: time

    def cobre(self, horario: Intervalo) -> bool:
        mesmo_dia = horario.inicio.date() == horario.fim.date()
        return mesmo_dia and self.inicio <= horario.inicio.time() and horario.fim.time() <= self.fim

    def acaba_em(self, horario: Intervalo) -> bool:
        return horario.fim.time() == self.fim


@dataclass(frozen=True)
class Profissional:
    id: str
    nome: str
    funcao: Funcao
    turno: Turno
    especialidade: str = ""

    def pode_ser_substituido_por(self, outro: "Profissional") -> bool:
        mesma_area = (outro.funcao, outro.especialidade) == (self.funcao, self.especialidade)
        return outro.id != self.id and mesma_area

    def cobre(self, horario: Intervalo) -> bool:
        return self.turno.cobre(horario)

    def turno_acaba_em(self, horario: Intervalo) -> bool:
        return self.turno.acaba_em(horario)


@dataclass(frozen=True)
class Procedimento:
    id: str
    nome: str
    duracao_min: int
    equipe_minima: tuple[tuple[Funcao, int], ...]
    instrumentos: tuple[tuple[str, int], ...]
    salas_permitidas: frozenset[str]
    higienizacao_min: int

    def permite_sala(self, sala_id: str) -> bool:
        return sala_id in self.salas_permitidas

    def quantidade_de(self, instrumento_id: str) -> int:
        return dict(self.instrumentos).get(instrumento_id, 0)


@dataclass(frozen=True)
class Indisponibilidade:
    tipo: TipoRecurso
    recurso_id: str
    periodo: Intervalo
    quantidade: int = 1

    def afeta(self, tipo: TipoRecurso, recurso_id: str, horario: Intervalo) -> bool:
        return (
            self.tipo == tipo and self.recurso_id == recurso_id and self.periodo.sobrepoe(horario)
        )


@dataclass(frozen=True)
class Cirurgia:
    id: str
    paciente_id: str
    procedimento_id: str
    sala_id: str
    horario: Intervalo
    equipe: frozenset[str]
    situacao: Situacao = Situacao.AGENDADA

    @property
    def ocupa_recursos(self) -> bool:
        return self.situacao.ocupa_recursos

    def simultanea(self, outra: "Cirurgia") -> bool:
        return (
            self.id != outra.id
            and self.ocupa_recursos
            and outra.ocupa_recursos
            and self.horario.sobrepoe(outra.horario)
        )

    def remarcada(self, horario: Intervalo | None = None, sala_id: str | None = None) -> "Cirurgia":
        return replace(self, horario=horario or self.horario, sala_id=sala_id or self.sala_id)

    def com_equipe(self, equipe: frozenset[str]) -> "Cirurgia":
        return replace(self, equipe=equipe)

    def com_situacao(self, situacao: Situacao) -> "Cirurgia":
        return replace(self, situacao=situacao)

    def situacao_em(self, momento: datetime) -> Situacao:
        """Situação pelo relógio: só agendadas e em andamento mudam com o tempo."""
        if not self.ocupa_recursos:
            return self.situacao
        if self.horario.fim <= momento:
            return Situacao.CONCLUIDA
        if self.horario.inicio <= momento:
            return Situacao.EM_ANDAMENTO
        return self.situacao
