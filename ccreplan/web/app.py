import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from flask import Flask

from ccreplan.dados_exemplo import agora, cadastros_de_exemplo, centro_de_exemplo
from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.persistencia import BancoDeDados
from ccreplan.replanejamento.ocorrencias import Analise
from ccreplan.replanejamento.opcoes import Opcao
from ccreplan.web.apresentacao import registrar_filtros
from ccreplan.web.rotas import rotas


@dataclass
class Clinica:
    """Estado da aplicação: fica dentro do objeto Flask, sem variáveis globais."""

    centro: CentroCirurgico
    banco: BancoDeDados
    pendente: tuple[Analise, list[Opcao]] | None = None

    def atualizar(self, centro: CentroCirurgico) -> None:
        self.centro = centro
        self.banco.salvar_programacao(centro)

    def sincronizar_com_o_relogio(self, momento: datetime) -> None:
        """Concluída, em andamento ou agendada conforme o horário."""
        atualizado = self.centro.com_situacoes_em(momento)
        if atualizado != self.centro:
            self.atualizar(atualizado)


def _programacao_de_hoje(banco: BancoDeDados, dia: date) -> CentroCirurgico:
    """Usa a programação salva; se ela não for de hoje, monta a de exemplo de hoje."""
    salva = banco.carregar_programacao(cadastros_de_exemplo())
    if salva and min(c.horario.inicio.date() for c in salva.cirurgias) == dia:
        return salva
    centro = centro_de_exemplo(dia)
    banco.salvar_programacao(centro)
    return centro


def _caminho_do_banco(app: Flask) -> Path:
    """Arquivo indicado em CCREPLAN_BANCO ou, por padrão, instance/ccreplan.sqlite3."""
    if "CCREPLAN_BANCO" in os.environ:
        return Path(os.environ["CCREPLAN_BANCO"])
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    return Path(app.instance_path) / "ccreplan.sqlite3"


def create_app(
    centro: CentroCirurgico | None = None,
    relogio: Callable[[], datetime] | None = None,
    banco: BancoDeDados | None = None,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("CCREPLAN_SECRET", "desenvolvimento")
    relogio = relogio or agora
    banco = banco or BancoDeDados(_caminho_do_banco(app))
    centro = centro or _programacao_de_hoje(banco, relogio().date())
    app.extensions["clinica"] = Clinica(centro, banco)
    app.extensions["relogio"] = relogio
    registrar_filtros(app)
    app.register_blueprint(rotas)
    return app
