"""Persistência em SQLite da programação do dia e do registro de auditoria."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ccreplan.dominio.centro import Cadastros, CentroCirurgico, Indisponibilidades
from ccreplan.dominio.modelos import Cirurgia, Indisponibilidade, Situacao, TipoRecurso
from ccreplan.dominio.tempo import Intervalo
from ccreplan.replanejamento.decisao import Decisao
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia
from ccreplan.replanejamento.opcoes import Opcao

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cirurgias (
    id TEXT PRIMARY KEY, paciente_id TEXT NOT NULL, procedimento_id TEXT NOT NULL,
    sala_id TEXT NOT NULL, inicio TEXT NOT NULL, fim TEXT NOT NULL,
    equipe TEXT NOT NULL, situacao TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS indisponibilidades (
    tipo TEXT NOT NULL, recurso_id TEXT NOT NULL,
    inicio TEXT NOT NULL, fim TEXT NOT NULL, quantidade INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS adiamentos (
    cirurgia_id TEXT PRIMARY KEY, inicio TEXT NOT NULL, fim TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, momento TEXT NOT NULL,
    tipo_ocorrencia TEXT NOT NULL, recurso_id TEXT NOT NULL,
    periodo_inicio TEXT NOT NULL, periodo_fim TEXT NOT NULL,
    descricao TEXT NOT NULL, quantidade INTEGER NOT NULL,
    opcao_adotada TEXT, opcoes TEXT NOT NULL,
    responsavel TEXT NOT NULL, justificativa TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS decisoes_nao_podem_ser_alteradas BEFORE UPDATE ON decisoes
BEGIN SELECT RAISE(ABORT, 'Decisões de auditoria não podem ser alteradas (NF15.1)'); END;
CREATE TRIGGER IF NOT EXISTS decisoes_nao_podem_ser_excluidas BEFORE DELETE ON decisoes
BEGIN SELECT RAISE(ABORT, 'Decisões de auditoria não podem ser excluídas (NF15.1)'); END;
"""


@dataclass(frozen=True)
class DecisaoRegistrada:
    """Decisão lida do banco, com o que a tela de auditoria precisa mostrar."""

    momento: datetime
    ocorrencia: Ocorrencia
    opcao_adotada: str | None
    opcoes: tuple[str, ...]
    responsavel: str
    justificativa: str

    @property
    def rejeitada(self) -> bool:
        return self.opcao_adotada is None


class BancoDeDados:
    """Guarda a programação e serve de registro de auditoria (mesma interface do em memória)."""

    def __init__(self, caminho: str | Path):
        self._caminho = Path(caminho)
        with self._transacao() as con:
            con.executescript(ESQUEMA)

    @contextmanager
    def _transacao(self):
        con = sqlite3.connect(self._caminho)
        try:
            with con:
                yield con
        finally:
            con.close()

    def salvar_programacao(self, centro: CentroCirurgico) -> None:
        with self._transacao() as con:
            con.execute("DELETE FROM cirurgias")
            con.execute("DELETE FROM indisponibilidades")
            con.execute("DELETE FROM adiamentos")
            con.executemany(
                "INSERT INTO cirurgias VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [_linha_da_cirurgia(c) for c in centro.cirurgias],
            )
            con.executemany(
                "INSERT INTO indisponibilidades VALUES (?, ?, ?, ?, ?)",
                [_linha_da_indisponibilidade(i) for i in centro.indisponibilidades],
            )
            con.executemany(
                "INSERT INTO adiamentos VALUES (?, ?, ?)",
                [(cid, *_periodo(original)) for cid, original in centro.adiamentos],
            )

    def carregar_programacao(self, cadastros: Cadastros) -> CentroCirurgico | None:
        with self._transacao() as con:
            cirurgias = con.execute("SELECT * FROM cirurgias ORDER BY rowid").fetchall()
            bloqueios = con.execute("SELECT * FROM indisponibilidades ORDER BY rowid").fetchall()
            adiamentos = con.execute("SELECT * FROM adiamentos ORDER BY rowid").fetchall()
        if not cirurgias:
            return None
        return CentroCirurgico(
            cadastros,
            tuple(_cirurgia(linha) for linha in cirurgias),
            Indisponibilidades(tuple(_indisponibilidade(linha) for linha in bloqueios)),
            tuple((cid, _intervalo(inicio, fim)) for cid, inicio, fim in adiamentos),
        )

    def registrar(self, decisao: Decisao) -> None:
        ocorrencia = decisao.ocorrencia
        opcoes = json.dumps([_opcao_em_dicionario(o) for o in decisao.opcoes], ensure_ascii=False)
        with self._transacao() as con:
            con.execute(
                "INSERT INTO decisoes (momento, tipo_ocorrencia, recurso_id, periodo_inicio,"
                " periodo_fim, descricao, quantidade, opcao_adotada, opcoes, responsavel,"
                " justificativa) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decisao.momento.isoformat(),
                    ocorrencia.tipo.name,
                    ocorrencia.recurso_id,
                    *_periodo(ocorrencia.periodo),
                    ocorrencia.descricao,
                    ocorrencia.quantidade,
                    decisao.opcao_adotada,
                    opcoes,
                    decisao.responsavel,
                    decisao.justificativa,
                ),
            )

    def decisoes(self) -> tuple[DecisaoRegistrada, ...]:
        with self._transacao() as con:
            linhas = con.execute("SELECT * FROM decisoes ORDER BY id").fetchall()
        return tuple(_decisao(linha) for linha in linhas)


def _periodo(intervalo: Intervalo) -> tuple[str, str]:
    return intervalo.inicio.isoformat(), intervalo.fim.isoformat()


def _intervalo(inicio: str, fim: str) -> Intervalo:
    return Intervalo(datetime.fromisoformat(inicio), datetime.fromisoformat(fim))


def _linha_da_cirurgia(c: Cirurgia) -> tuple:
    return (c.id, c.paciente_id, c.procedimento_id, c.sala_id, *_periodo(c.horario),
            ",".join(sorted(c.equipe)), c.situacao.name)  # fmt: skip


def _cirurgia(linha) -> Cirurgia:
    cid, paciente, procedimento, sala, inicio, fim, equipe, situacao = linha
    return Cirurgia(cid, paciente, procedimento, sala, _intervalo(inicio, fim),
                    frozenset(equipe.split(",")), Situacao[situacao])  # fmt: skip


def _linha_da_indisponibilidade(i: Indisponibilidade) -> tuple:
    return (i.tipo.name, i.recurso_id, *_periodo(i.periodo), i.quantidade)


def _indisponibilidade(linha) -> Indisponibilidade:
    tipo, recurso, inicio, fim, quantidade = linha
    return Indisponibilidade(TipoRecurso[tipo], recurso, _intervalo(inicio, fim), quantidade)


def _opcao_em_dicionario(opcao: Opcao) -> dict:
    impacto = opcao.impacto
    return {
        "descricao": opcao.descricao,
        "tempo_sala_perdido_min": impacto.tempo_sala_perdido_min,
        "pacientes_afetados": impacto.pacientes_afetados,
        "restricoes_no_limite": list(impacto.restricoes_no_limite),
        "movimentos": [
            {"cirurgia": m.original.id, "de": _linha_da_cirurgia(m.original),
             "para": _linha_da_cirurgia(m.nova)}
            for m in opcao.movimentos
        ],
    }  # fmt: skip


def _decisao(linha) -> DecisaoRegistrada:
    _, momento, tipo, recurso, inicio, fim, descricao, quantidade, adotada, opcoes, *pessoa = linha
    ocorrencia = Ocorrencia(
        TipoOcorrencia[tipo], recurso, _intervalo(inicio, fim), descricao, quantidade
    )
    nomes = tuple(o["descricao"] for o in json.loads(opcoes))
    return DecisaoRegistrada(datetime.fromisoformat(momento), ocorrencia, adotada, nomes, *pessoa)
