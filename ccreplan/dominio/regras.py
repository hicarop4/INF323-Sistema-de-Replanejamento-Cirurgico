"""Regras de validação do agendamento.

Cada regra é uma classe pequena. O mesmo Validador é usado para agendar, para descobrir as cirurgias
afetadas por uma ocorrência e para garantir que as opções de replanejamento são válidas.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.dominio.modelos import Cirurgia, TipoRecurso


def _sem_repeticao(textos) -> tuple[str, ...]:
    return tuple(dict.fromkeys(textos))


@dataclass(frozen=True)
class Verificacao:
    violacoes: tuple[str, ...] = ()
    limites: tuple[str, ...] = ()

    @property
    def valida(self) -> bool:
        return not self.violacoes

    def __add__(self, outra: "Verificacao") -> "Verificacao":
        return Verificacao(
            _sem_repeticao(self.violacoes + outra.violacoes),
            _sem_repeticao(self.limites + outra.limites),
        )


class Regra(Protocol):
    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao: ...


class RegraEquipe:
    """A equipe tem os profissionais exigidos e todos estão disponíveis."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        return self._faltas(cirurgia, centro) + self._disponibilidade(cirurgia, centro)

    @staticmethod
    def _faltas(cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        presentes = Counter(centro.cadastros.profissional(pid).funcao for pid in cirurgia.equipe)
        exigidas = centro.procedimento_de(cirurgia).equipe_minima
        return Verificacao(
            tuple(
                f"Falta {funcao.value} na equipe"
                for funcao, qtd in exigidas
                if presentes[funcao] < qtd
            )
        )

    @staticmethod
    def _disponibilidade(cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        violacoes, limites = [], []
        for pid in sorted(cirurgia.equipe):
            profissional = centro.cadastros.profissional(pid)
            if not profissional.cobre(cirurgia.horario):
                violacoes.append(f"{profissional.nome} fora do turno")
            elif centro.indisponibilidades.bloqueia(
                TipoRecurso.PROFISSIONAL, pid, cirurgia.horario
            ):
                violacoes.append(f"{profissional.nome} indisponível")
            elif profissional.turno_acaba_em(cirurgia.horario):
                limites.append(f"turno de {profissional.nome}")
        return Verificacao(tuple(violacoes), tuple(limites))


class RegraConflitoDeHorario:
    """Sala, profissionais e paciente não podem estar em duas cirurgias ao mesmo tempo."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        violacoes = []
        for outra in centro.simultaneas(cirurgia):
            violacoes += self._conflitos(cirurgia, outra, centro)
        return Verificacao(_sem_repeticao(violacoes))

    @staticmethod
    def _conflitos(cirurgia: Cirurgia, outra: Cirurgia, centro: CentroCirurgico) -> list[str]:
        cadastros = centro.cadastros
        conflitos = [
            f"{cadastros.profissional(pid).nome} já está em outra cirurgia"
            for pid in sorted(cirurgia.equipe & outra.equipe)
        ]
        if outra.sala_id == cirurgia.sala_id:
            conflitos.insert(0, f"{cadastros.sala(cirurgia.sala_id).nome} ocupada")
        if outra.paciente_id == cirurgia.paciente_id:
            paciente = cadastros.paciente(cirurgia.paciente_id)
            conflitos.append(f"Paciente {paciente.nome} já está em outra cirurgia")
        return conflitos


class RegraSala:
    """A sala é permitida para o procedimento e não está bloqueada."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        sala = centro.cadastros.sala(cirurgia.sala_id)
        violacoes = []
        if not centro.procedimento_de(cirurgia).permite_sala(sala.id):
            violacoes.append(f"Procedimento não pode ser feito na sala {sala.nome}")
        if centro.indisponibilidades.bloqueia(TipoRecurso.SALA, sala.id, cirurgia.horario):
            violacoes.append(f"{sala.nome} indisponível")
        return Verificacao(tuple(violacoes))


class RegraPaciente:
    """O paciente não está indisponível no horário da cirurgia."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        if not centro.indisponibilidades.bloqueia(
            TipoRecurso.PACIENTE, cirurgia.paciente_id, cirurgia.horario
        ):
            return Verificacao()
        paciente = centro.cadastros.paciente(cirurgia.paciente_id)
        return Verificacao((f"Paciente {paciente.nome} indisponível",))


class RegraInstrumentos:
    """Há instrumentos disponíveis para esta e para as cirurgias simultâneas."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        violacoes, limites = [], []
        simultaneas = centro.simultaneas(cirurgia)
        for iid, quantidade in centro.procedimento_de(cirurgia).instrumentos:
            instrumento = centro.cadastros.instrumento(iid)
            demanda = quantidade + sum(
                centro.procedimento_de(o).quantidade_de(iid) for o in simultaneas
            )
            disponivel = instrumento.quantidade - centro.indisponibilidades.quantidade(
                iid, cirurgia.horario
            )
            if demanda > disponivel:
                violacoes.append(f"{instrumento.nome} insuficiente")
            elif demanda == disponivel:
                limites.append(f"{instrumento.nome} no limite")
        return Verificacao(tuple(violacoes), tuple(limites))


class RegraHigienizacao:
    """Entre duas cirurgias na mesma sala é cumprido o tempo mínimo de higienização."""

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        nome_sala = centro.cadastros.sala(cirurgia.sala_id).nome
        violacoes, limites = [], []
        for outra in centro.na_mesma_sala(cirurgia):
            anterior, seguinte = sorted((cirurgia, outra), key=lambda c: c.horario.inicio)
            folga = anterior.horario.minutos_ate(seguinte.horario.inicio)
            exigido = centro.procedimento_de(anterior).higienizacao_min
            if 0 <= folga < exigido:
                violacoes.append(f"Higienização da {nome_sala} não cumprida")
            elif folga == exigido:
                limites.append(f"limpeza da {nome_sala}")
        return Verificacao(_sem_repeticao(violacoes), _sem_repeticao(limites))


REGRAS_PADRAO: tuple[Regra, ...] = (
    RegraEquipe(),
    RegraConflitoDeHorario(),
    RegraSala(),
    RegraPaciente(),
    RegraInstrumentos(),
    RegraHigienizacao(),
)


class Validador:
    def __init__(self, regras: tuple[Regra, ...] = REGRAS_PADRAO):
        self._regras = regras

    def verificar(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> Verificacao:
        return sum((regra.verificar(cirurgia, centro) for regra in self._regras), Verificacao())

    def e_valida(self, cirurgia: Cirurgia, centro: CentroCirurgico) -> bool:
        return self.verificar(cirurgia, centro).valida
