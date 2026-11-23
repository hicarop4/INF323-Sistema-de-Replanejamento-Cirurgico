"""Decidir replanejamento e Registrar decisão para auditoria."""

from dataclasses import dataclass
from datetime import datetime

from ccreplan.dominio.centro import CentroCirurgico
from ccreplan.replanejamento.ocorrencias import Analise, Ocorrencia
from ccreplan.replanejamento.opcoes import Opcao


class DecisaoInvalida(ValueError):
    pass


@dataclass(frozen=True)
class PedidoDeDecisao:
    responsavel: str
    justificativa: str
    momento: datetime
    confirmado: bool


@dataclass(frozen=True)
class Decisao:
    ocorrencia: Ocorrencia
    opcoes: tuple[Opcao, ...]
    escolhida: Opcao | None
    responsavel: str
    justificativa: str
    momento: datetime

    @property
    def rejeitada(self) -> bool:
        return self.escolhida is None

    @property
    def opcao_adotada(self) -> str | None:
        return None if self.escolhida is None else self.escolhida.descricao


class RegistroAuditoria:
    """Só permite incluir e consultar decisões (NF15.1)."""

    def __init__(self):
        self._decisoes: list[Decisao] = []

    def registrar(self, decisao: Decisao) -> None:
        self._decisoes.append(decisao)

    def decisoes(self) -> tuple[Decisao, ...]:
        return tuple(self._decisoes)


def decidir(
    analise: Analise,
    opcoes: list[Opcao],
    indice: int | None,
    pedido: PedidoDeDecisao,
    auditoria: RegistroAuditoria,
) -> CentroCirurgico:
    """Aplica a opção escolhida (ou nenhuma, se `indice` for None) e registra a decisão."""
    if not pedido.confirmado:
        raise DecisaoInvalida("Nenhuma opção é aplicada sem a confirmação do funcionário")
    justificativa = pedido.justificativa.strip()
    if not justificativa:
        raise DecisaoInvalida("Informe uma justificativa para a decisão")
    escolhida = None if indice is None else opcoes[indice]
    auditoria.registrar(
        Decisao(
            analise.ocorrencia,
            tuple(opcoes),
            escolhida,
            pedido.responsavel,
            justificativa,
            pedido.momento,
        )
    )
    return escolhida.aplicar_em(analise.centro) if escolhida else analise.centro
