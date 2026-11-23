"""Programação simulada da Clínica São Lucas, no plano Básico (até 3 salas). """




from datetime import date, datetime, time, timedelta

from ccreplan.dominio.centro import Cadastros, CentroCirurgico
from ccreplan.dominio.modelos import (
    Cirurgia,
    Funcao,
    Instrumento,
    Paciente,
    Procedimento,
    Profissional,
    Sala,
    Turno,
)
from ccreplan.dominio.tempo import Intervalo

RESPONSAVEL = "Ana Souza"

C, A, E, INS = Funcao.CIRURGIAO, Funcao.ANESTESISTA, Funcao.ENFERMEIRO, Funcao.INSTRUMENTADOR
EQUIPE_BASICA = ((C, 1), (A, 1), (E, 1))
TODAS_AS_SALAS = frozenset({"S1", "S2", "S3"})


def agora() -> datetime:
    """Relógio real, em minutos: a situação das cirurgias é calculada a partir dele."""
    return datetime.now().replace(second=0, microsecond=0)


def _as(dia: date, hhmm: str) -> datetime:
    return datetime.combine(dia, time.fromisoformat(hhmm))


PACIENTES = (
    ("M.A.A.", "Maria Aparecida Alves"),
    ("R.C.P.", "Roberto Carlos Pereira"),
    ("C.R.B.", "Camila Rodrigues Barbosa"),
    ("P.F.O.", "Paulo Fernando Oliveira"),
    ("J.S.L.", "Jéssica Santos Lima"),
    ("L.M.", "Luiza Martins"),
    ("T.G.N.", "Tiago Gomes Nunes"),
    ("V.H.A.", "Vitor Hugo Araújo"),
    ("A.P.S.", "Ana Paula Silva"),
    ("J.C.R.", "João Carlos Ribeiro"),
    ("F.M.T.", "Fernando Moreira Tavares"),
    ("B.L.C.", "Bruna Lopes Costa"),
    ("E.S.M.", "Eduardo Santos Melo"),
    ("R.A.S.", "Rita Alves Santos"),
    ("G.H.M.", "Gustavo Henrique Moura"),
    ("L.F.C.", "Larissa Freitas Cardoso"),
    ("M.V.P.", "Marcos Vinícius Prado"),
    ("N.C.D.", "Natália Cristina Dias"),
    ("O.S.R.", "Otávio Silva Rocha"),
    ("P.M.L.", "Priscila Mendes Lopes"),
    ("Q.A.B.", "Quitéria Andrade Borges"),
    ("S.T.F.", "Samuel Teixeira Fonseca"),
    ("U.R.G.", "Úrsula Ramos Gomes"),
    ("V.L.N.", "Valéria Lima Nogueira"),
    ("W.C.A.", "Wagner Costa Azevedo"),
    ("Y.M.S.", "Yara Moreira Souza"),
    ("Z.P.R.", "Zeca Pereira Ramos"),
    ("A.B.C.", "Alice Barbosa Cunha"),
    ("D.F.G.", "Diego Ferreira Gomes"),
)


def cadastros_de_exemplo() -> Cadastros:
    turno = Turno(time(7), time(19))
    pessoas = [
        ("helena", "Dra. Helena Rocha", C, "cirurgia geral"),
        ("andre", "Dr. André Melo", C, "cirurgia geral"),
        ("rafael", "Dr. Rafael Costa", C, "ginecologia e obstetrícia"),
        ("carlos", "Dr. Carlos Lima", C, "ortopedia"),
        ("marina", "Dra. Marina Duarte", C, "neurocirurgia"),
        ("paulo", "Dr. Paulo Mendes", A, ""),
        ("lucia", "Dra. Lúcia Faria", A, ""),
        ("sergio", "Dr. Sérgio Lopes", A, ""),
        ("beatriz", "Dra. Beatriz Nogueira", A, ""),
        ("marcos", "Marcos Teixeira", E, ""),
        ("carla", "Carla Dias", E, ""),
        ("bruno", "Bruno Alves", E, ""),
        ("fernanda", "Fernanda Souza", E, ""),
        ("juliana", "Juliana Prado", INS, ""),
        ("pedro", "Pedro Nunes", INS, ""),
    ]
    procedimentos = [
        Procedimento("colecistectomia", "Colecistectomia", 90, EQUIPE_BASICA,
                     (("pinca", 2),), TODAS_AS_SALAS, 30),
        Procedimento("herniorrafia", "Herniorrafia", 60, EQUIPE_BASICA,
                     (("afastador", 1),), TODAS_AS_SALAS, 30),
        Procedimento("cesariana", "Cesariana", 60, (*EQUIPE_BASICA, (INS, 1)),
                     (("pinca", 2),), frozenset({"S1", "S3"}), 30),
        Procedimento("artroplastia", "Artroplastia", 120, (*EQUIPE_BASICA, (INS, 1)),
                     (("afastador", 1), ("porta-agulha", 2)), frozenset({"S2", "S3"}), 60),
        Procedimento("microdiscectomia", "Microdiscectomia", 120, (*EQUIPE_BASICA, (INS, 1)),
                     (("afastador", 1),), frozenset({"S2", "S3"}), 30),
    ]  # fmt: skip
    return Cadastros(
        salas=(Sala("S1", "Sala 01"), Sala("S2", "Sala 02"), Sala("S3", "Sala 03")),
        profissionais=tuple(
            Profissional(pid, nome, f, turno, esp) for pid, nome, f, esp in pessoas
        ),
        instrumentos=(
            Instrumento("pinca", "Pinça Kelly", 4),
            Instrumento("afastador", "Afastador Farabeuf", 2),
            Instrumento("porta-agulha", "Porta-agulha", 2),
        ),
        procedimentos=tuple(procedimentos),
        pacientes=tuple(Paciente(pid, nome) for pid, nome in PACIENTES),
    )


AGENDA_HOJE = [
    ("c1", "M.A.A.", "colecistectomia", "S1", "09:00", "helena paulo marcos"),
    ("c2", "R.C.P.", "herniorrafia", "S2", "09:30", "andre sergio bruno"),
    ("c3", "C.R.B.", "cesariana", "S3", "08:00", "rafael sergio bruno juliana"),
    ("c4", "P.F.O.", "herniorrafia", "S3", "11:00", "andre lucia carla"),
    ("c5", "J.S.L.", "cesariana", "S1", "12:00", "rafael lucia carla juliana"),
    ("c6", "L.M.", "artroplastia", "S2", "13:00", "carlos paulo marcos pedro"),
    ("c7", "T.G.N.", "colecistectomia", "S3", "15:00", "andre sergio bruno"),
    ("c8", "V.H.A.", "herniorrafia", "S2", "07:30", "helena beatriz fernanda"),
    ("c9", "A.P.S.", "herniorrafia", "S1", "13:30", "andre beatriz fernanda"),
    ("c10", "J.C.R.", "colecistectomia", "S1", "15:30", "helena lucia carla"),
    ("c11", "F.M.T.", "microdiscectomia", "S2", "16:00", "marina paulo marcos pedro"),
    ("c12", "B.L.C.", "cesariana", "S3", "17:00", "rafael sergio bruno juliana"),
    ("c13", "E.S.M.", "herniorrafia", "S1", "18:00", "andre beatriz fernanda"),
]  # fmt: skip

AGENDA_AMANHA = [
    ("c14", "R.A.S.", "colecistectomia", "S1", "07:30", "helena paulo marcos"),
    ("c15", "G.H.M.", "herniorrafia", "S1", "09:30", "andre lucia carla"),
    ("c16", "L.F.C.", "cesariana", "S1", "11:00", "rafael sergio bruno juliana"),
    ("c17", "M.V.P.", "colecistectomia", "S1", "14:00", "helena paulo marcos"),
    ("c18", "N.C.D.", "artroplastia", "S2", "08:00", "carlos beatriz fernanda pedro"),
    ("c19", "O.S.R.", "microdiscectomia", "S2", "11:00", "marina paulo marcos pedro"),
    ("c20", "P.M.L.", "herniorrafia", "S2", "15:00", "andre lucia carla"),
    ("c21", "Q.A.B.", "cesariana", "S3", "08:00", "rafael sergio bruno juliana"),
    ("c22", "S.T.F.", "herniorrafia", "S3", "10:30", "helena beatriz fernanda"),
    ("c23", "U.R.G.", "artroplastia", "S3", "13:00", "carlos beatriz fernanda pedro"),
]  # fmt: skip

AGENDA_DEPOIS_DE_AMANHA = [
    ("c24", "V.L.N.", "cesariana", "S1", "08:00", "rafael lucia carla juliana"),
    ("c25", "W.C.A.", "colecistectomia", "S1", "10:00", "andre sergio bruno"),
    ("c26", "Y.M.S.", "herniorrafia", "S1", "13:00", "helena paulo marcos"),
    ("c27", "Z.P.R.", "microdiscectomia", "S2", "09:00", "marina beatriz fernanda pedro"),
    ("c28", "A.B.C.", "artroplastia", "S2", "14:00", "carlos paulo marcos pedro"),
    ("c29", "D.F.G.", "herniorrafia", "S3", "08:30", "helena sergio bruno"),
]  # fmt: skip

AGENDAS = (AGENDA_HOJE, AGENDA_AMANHA, AGENDA_DEPOIS_DE_AMANHA)


def centro_de_exemplo(dia: date | None = None) -> CentroCirurgico:
    """Programação de hoje (ou do dia pedido) e dos dois dias seguintes."""
    dia = dia or date.today()
    cadastros = cadastros_de_exemplo()
    cirurgias = tuple(
        _cirurgia(cadastros, dia + timedelta(days=deslocamento), linha)
        for deslocamento, agenda in enumerate(AGENDAS)
        for linha in agenda
    )
    return CentroCirurgico(cadastros, cirurgias)


def _cirurgia(cadastros: Cadastros, dia: date, linha: tuple) -> Cirurgia:
    cid, paciente, proc, sala, inicio, equipe = linha
    duracao = cadastros.procedimento(proc).duracao_min
    horario = Intervalo.a_partir(_as(dia, inicio), duracao)
    equipe = frozenset(equipe.split())
    return Cirurgia(cid, paciente, proc, sala, horario, equipe)
