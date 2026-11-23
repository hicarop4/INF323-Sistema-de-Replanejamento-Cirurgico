from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import cached_property

from ccreplan.dominio.modelos import (
    Cirurgia,
    Indisponibilidade,
    Instrumento,
    Paciente,
    Procedimento,
    Profissional,
    Sala,
    Situacao,
    TipoRecurso,
)
from ccreplan.dominio.tempo import Intervalo


def _por_id(itens) -> dict:
    return {item.id: item for item in itens}


@dataclass(frozen=True)
class Cadastros:
    """Dados mantidos pelos CRUDs, uso aqui só para consulta."""

    salas: tuple[Sala, ...]
    profissionais: tuple[Profissional, ...]
    instrumentos: tuple[Instrumento, ...]
    procedimentos: tuple[Procedimento, ...]
    pacientes: tuple[Paciente, ...]

    @cached_property
    def _indice(self) -> dict[str, dict]:
        return {
            "sala": _por_id(self.salas),
            "profissional": _por_id(self.profissionais),
            "instrumento": _por_id(self.instrumentos),
            "procedimento": _por_id(self.procedimentos),
            "paciente": _por_id(self.pacientes),
        }

    def sala(self, sid: str) -> Sala:
        return self._indice["sala"].get(sid, Sala(sid, sid))

    def profissional(self, pid: str) -> Profissional:
        return self._indice["profissional"][pid]

    def instrumento(self, iid: str) -> Instrumento:
        return self._indice["instrumento"][iid]

    def procedimento(self, pid: str) -> Procedimento:
        return self._indice["procedimento"][pid]

    def paciente(self, pid: str) -> Paciente:
        return self._indice["paciente"][pid]


@dataclass(frozen=True)
class Indisponibilidades:
    """Recursos fora de uso: ausências, salas, instrumentos e pacientes indisponíveis."""

    itens: tuple[Indisponibilidade, ...] = ()

    def __iter__(self):
        return iter(self.itens)

    def __len__(self) -> int:
        return len(self.itens)

    def bloqueia(self, tipo: TipoRecurso, recurso_id: str, horario: Intervalo) -> bool:
        return any(i.afeta(tipo, recurso_id, horario) for i in self.itens)

    def quantidade(self, instrumento_id: str, horario: Intervalo) -> int:
        afetam = (
            i for i in self.itens if i.afeta(TipoRecurso.INSTRUMENTO, instrumento_id, horario)
        )
        return sum(i.quantidade for i in afetam)

    def com(self, indisponibilidade: Indisponibilidade) -> "Indisponibilidades":
        return Indisponibilidades((*self.itens, indisponibilidade))


@dataclass(frozen=True)
class CentroCirurgico:
    """Cadastros, cirurgias, recursos indisponíveis e horários anteriores aos adiamentos."""

    cadastros: Cadastros
    cirurgias: tuple[Cirurgia, ...]
    indisponibilidades: Indisponibilidades = field(default_factory=Indisponibilidades)
    adiamentos: tuple[tuple[str, Intervalo], ...] = ()

    def cirurgia(self, cid: str) -> Cirurgia:
        return next(c for c in self.cirurgias if c.id == cid)

    def procedimento_de(self, cirurgia: Cirurgia) -> Procedimento:
        return self.cadastros.procedimento(cirurgia.procedimento_id)

    def agendadas(self) -> list[Cirurgia]:
        return sorted(
            (c for c in self.cirurgias if c.situacao is Situacao.AGENDADA),
            key=lambda c: (c.horario.inicio, c.sala_id),
        )

    def simultaneas(self, cirurgia: Cirurgia) -> list[Cirurgia]:
        return [outra for outra in self.cirurgias if cirurgia.simultanea(outra)]

    def na_mesma_sala(self, cirurgia: Cirurgia) -> list[Cirurgia]:
        return [
            outra
            for outra in self.cirurgias
            if outra.id != cirurgia.id
            and outra.ocupa_recursos
            and outra.sala_id == cirurgia.sala_id
        ]

    def com_cirurgia(self, nova: Cirurgia) -> "CentroCirurgico":
        cirurgias = tuple(nova if c.id == nova.id else c for c in self.cirurgias)
        return replace(self, cirurgias=cirurgias)

    def com_situacoes_em(self, momento: datetime) -> "CentroCirurgico":
        cirurgias = tuple(c.com_situacao(c.situacao_em(momento)) for c in self.cirurgias)
        return replace(self, cirurgias=cirurgias)

    def horario_original(self, cid: str) -> Intervalo | None:
        """Horário que a cirurgia tinha antes de ser adiada (None se nunca foi adiada)."""
        return dict(self.adiamentos).get(cid)

    def com_adiamento(self, cid: str, original: Intervalo) -> "CentroCirurgico":
        if self.horario_original(cid) is not None:
            return self  # guarda sempre o primeiro horário
        return replace(self, adiamentos=(*self.adiamentos, (cid, original)))

    def com_indisponibilidade(self, indisponibilidade: Indisponibilidade) -> "CentroCirurgico":
        return replace(self, indisponibilidades=self.indisponibilidades.com(indisponibilidade))
