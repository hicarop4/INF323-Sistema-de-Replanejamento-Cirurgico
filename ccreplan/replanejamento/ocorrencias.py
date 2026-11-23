"""Registrar ocorrência e identificar as cirurgias afetadas."""

from dataclasses import dataclass
from enum import Enum

from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.dominio.modelos import Cirurgia, Indisponibilidade, Situacao, TipoRecurso
from ccreplan.dominio.regras import Validador
from ccreplan.dominio.tempo import Intervalo


class TipoOcorrencia(Enum):
    AUSENCIA_PROFISSIONAL = "Ausência de profissional"
    SALA_INDISPONIVEL = "Sala indisponível"
    INSTRUMENTO_INDISPONIVEL = "Instrumento indisponível"
    PACIENTE_INDISPONIVEL = "Paciente indisponível"
    ATRASO_CIRURGIA = "Atraso de cirurgia"

    @property
    def recurso(self) -> TipoRecurso | None:
        return _RECURSO_AFETADO.get(self)


_RECURSO_AFETADO = {
    TipoOcorrencia.AUSENCIA_PROFISSIONAL: TipoRecurso.PROFISSIONAL,
    TipoOcorrencia.SALA_INDISPONIVEL: TipoRecurso.SALA,
    TipoOcorrencia.INSTRUMENTO_INDISPONIVEL: TipoRecurso.INSTRUMENTO,
    TipoOcorrencia.PACIENTE_INDISPONIVEL: TipoRecurso.PACIENTE,
}


@dataclass(frozen=True)
class Ocorrencia:
    """Acontecimento que afeta a programação do dia.

    `periodo` vai do registro até o fim do tempo em que o recurso fica afetado. No atraso de
    cirurgia, `recurso_id` é a cirurgia atrasada e a duração do período é o atraso.
    """

    tipo: TipoOcorrencia
    recurso_id: str
    periodo: Intervalo
    descricao: str = ""
    quantidade: int = 1

    def aplicar(self, centro: CentroCirurgico) -> CentroCirurgico:
        if self.tipo is TipoOcorrencia.ATRASO_CIRURGIA:
            return self._atrasar(centro)
        bloqueio = Indisponibilidade(
            self.tipo.recurso, self.recurso_id, self.periodo, self.quantidade
        )
        return centro.com_indisponibilidade(bloqueio)

    def _atrasar(self, centro: CentroCirurgico) -> CentroCirurgico:
        cirurgia = centro.cirurgia(self.recurso_id)
        horario = cirurgia.horario.estendido(self.periodo.duracao_min)
        return centro.com_cirurgia(cirurgia.remarcada(horario).com_situacao(Situacao.EM_ANDAMENTO))


@dataclass(frozen=True)
class Analise:
    ocorrencia: Ocorrencia
    centro: CentroCirurgico
    afetadas: tuple[Cirurgia, ...]


def analisar(
    ocorrencia: Ocorrencia, centro: CentroCirurgico, validador: Validador | None = None
) -> Analise:
    """Aplica a ocorrência e devolve as cirurgias que ficaram inválidas por causa dela."""
    validador = validador or Validador()
    depois = ocorrencia.aplicar(centro)
    afetadas = tuple(
        cirurgia
        for cirurgia in depois.agendadas()
        if validador.e_valida(centro.cirurgia(cirurgia.id), centro)
        and not validador.e_valida(cirurgia, depois)
    )
    return Analise(ocorrencia, depois, afetadas)
