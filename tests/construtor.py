"""Construtor de cenários de teste: evita repetir a montagem do centro cirúrgico em cada teste."""

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta

from ccreplan.dominio.centro import Cadastros, CentroCirurgico, Indisponibilidades
from ccreplan.dominio.modelos import (
    Cirurgia,
    Funcao,
    Indisponibilidade,
    Instrumento,
    Paciente,
    Procedimento,
    Profissional,
    Sala,
    Situacao,
    TipoRecurso,
    Turno,
)
from ccreplan.dominio.tempo import Intervalo

DIA = datetime(2026, 10, 11)
EQUIPE_PADRAO = ("cir1", "anest1", "enf1")


def hora(hhmm: str) -> datetime:
    horas, minutos = (int(parte) for parte in hhmm.split(":"))
    return DIA + timedelta(hours=horas, minutes=minutos)


def intervalo(inicio: str, fim: str) -> Intervalo:
    return Intervalo(hora(inicio), hora(fim))


def _profissionais() -> dict[str, Profissional]:
    turno = Turno(time(7), time(19))
    pessoas = [
        ("cir1", "Dra. Helena Rocha", Funcao.CIRURGIAO),
        ("cir2", "Dr. Rafael Costa", Funcao.CIRURGIAO),
        ("anest1", "Dr. Paulo Mendes", Funcao.ANESTESISTA),
        ("anest2", "Dra. Lúcia Faria", Funcao.ANESTESISTA),
        ("enf1", "Marcos Teixeira", Funcao.ENFERMEIRO),
        ("enf2", "Carla Dias", Funcao.ENFERMEIRO),
    ]
    return {pid: Profissional(pid, nome, funcao, turno) for pid, nome, funcao in pessoas}


def _procedimento_padrao() -> Procedimento:
    return Procedimento(
        id="colecistectomia",
        nome="Colecistectomia",
        duracao_min=60,
        equipe_minima=((Funcao.CIRURGIAO, 1), (Funcao.ANESTESISTA, 1), (Funcao.ENFERMEIRO, 1)),
        instrumentos=(("pinca", 2),),
        salas_permitidas=frozenset({"S1", "S2", "S3"}),
        higienizacao_min=30,
    )


@dataclass
class Cenario:
    """Monta um CentroCirurgico com valores padrão que cada teste pode sobrescrever."""

    salas: list = field(default_factory=lambda: ["S1", "S2", "S3"])
    profissionais: dict = field(default_factory=_profissionais)
    instrumentos: dict = field(
        default_factory=lambda: {"pinca": Instrumento("pinca", "Pinça Kelly", 4)}
    )
    procedimentos: dict = field(default_factory=lambda: {"colecistectomia": _procedimento_padrao()})
    cirurgias: list = field(default_factory=list)
    indisponibilidades: list = field(default_factory=list)

    def com_cirurgia(self, cid: str, inicio: str = "08:00", **campos) -> "Cenario":
        procedimento = self.procedimentos[campos.pop("procedimento", "colecistectomia")]
        cirurgia = Cirurgia(
            id=cid,
            paciente_id=campos.pop("paciente", f"pac-{cid}"),
            procedimento_id=procedimento.id,
            sala_id=campos.pop("sala", "S1"),
            horario=Intervalo.a_partir(hora(inicio), procedimento.duracao_min),
            equipe=frozenset(campos.pop("equipe", EQUIPE_PADRAO)),
            situacao=campos.pop("situacao", Situacao.AGENDADA),
        )
        self.cirurgias.append(cirurgia)
        return self

    def com_profissional(self, pid: str, nome: str, funcao: Funcao) -> "Cenario":
        self.profissionais[pid] = Profissional(pid, nome, funcao, Turno(time(7), time(19)))
        return self

    def com_especialidade(self, pid: str, especialidade: str) -> "Cenario":
        self.profissionais[pid] = replace(self.profissionais[pid], especialidade=especialidade)
        return self

    def com_turno(self, pid: str, inicio: str, fim: str) -> "Cenario":
        turno = Turno(time.fromisoformat(inicio), time.fromisoformat(fim))
        self.profissionais[pid] = replace(self.profissionais[pid], turno=turno)
        return self

    def com_estoque(self, iid: str, quantidade: int) -> "Cenario":
        self.instrumentos[iid] = replace(self.instrumentos[iid], quantidade=quantidade)
        return self

    def com_procedimento(self, procedimento: Procedimento) -> "Cenario":
        self.procedimentos[procedimento.id] = procedimento
        return self

    def indisponivel(self, tipo: TipoRecurso, rid: str, periodo: Intervalo, quantidade: int = 1):
        self.indisponibilidades.append(Indisponibilidade(tipo, rid, periodo, quantidade))
        return self

    def construir(self) -> CentroCirurgico:
        pacientes = {
            c.paciente_id: Paciente(c.paciente_id, c.paciente_id.upper()) for c in self.cirurgias
        }
        cadastros = Cadastros(
            salas=tuple(Sala(sid, f"Sala {sid[1:].zfill(2)}") for sid in self.salas),
            profissionais=tuple(self.profissionais.values()),
            instrumentos=tuple(self.instrumentos.values()),
            procedimentos=tuple(self.procedimentos.values()),
            pacientes=tuple(pacientes.values()),
        )
        bloqueios = Indisponibilidades(tuple(self.indisponibilidades))
        return CentroCirurgico(cadastros, tuple(self.cirurgias), bloqueios)
