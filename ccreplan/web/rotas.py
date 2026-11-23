from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request

from ccreplan.dados_exemplo import RESPONSAVEL
from ccreplan.dominio.tempo import Intervalo
from ccreplan.replanejamento.decisao import DecisaoInvalida, PedidoDeDecisao, decidir
from ccreplan.replanejamento.ocorrencias import Ocorrencia, TipoOcorrencia, analisar
from ccreplan.replanejamento.opcoes import PLANOS_CANCELAMENTO, PLANOS_PADRAO, gerar_opcoes
from ccreplan.web.apresentacao import proximos_dias, recurso_combina_com_o_tipo, recursos_por_tipo

rotas = Blueprint("rotas", __name__)
PERIODO_PADRAO = timedelta(hours=2)
FORMATO_CAMPO = "%Y-%m-%dT%H:%M"


def _clinica():
    return current_app.extensions["clinica"]


def _agora():
    return current_app.extensions["relogio"]()


def _quer_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


def _avisar(mensagem: str, voltar_para: str, status: int = 400):
    """Com JavaScript, responde o aviso em JSON e o formulário fica como estava."""
    if _quer_json():
        return jsonify(mensagem=mensagem), status
    flash(mensagem)
    return redirect(voltar_para)


def _seguir_para(destino: str):
    return jsonify(proxima=destino) if _quer_json() else redirect(destino)


def _ler_ocorrencia(form) -> Ocorrencia | None:
    try:
        tipo = TipoOcorrencia[form["tipo"]]
        periodo = Intervalo(
            datetime.strptime(form["inicio"], FORMATO_CAMPO),
            datetime.strptime(form["fim"], FORMATO_CAMPO),
        )
        quantidade = int(form.get("quantidade") or 1)
    except (KeyError, ValueError):
        return None
    recurso = form.get("recurso", "").strip()
    if not recurso:
        return None
    return Ocorrencia(tipo, recurso, periodo, form.get("descricao", "").strip(), quantidade)


@rotas.before_request
def sincronizar_situacoes():
    _clinica().sincronizar_com_o_relogio(_agora())


@rotas.get("/")
def inicio():
    clinica = _clinica()
    return render_template(
        "inicio.html",
        centro=clinica.centro,
        decisoes=clinica.banco.decisoes(),
        tipos=TipoOcorrencia,
        recursos=recursos_por_tipo(clinica.centro),
        dias=proximos_dias(_agora().date()),
        inicio_padrao=_agora().strftime(FORMATO_CAMPO),
        fim_padrao=(_agora() + PERIODO_PADRAO).strftime(FORMATO_CAMPO),
    )


@rotas.post("/ocorrencias")
def registrar_ocorrencia():
    ocorrencia = _ler_ocorrencia(request.form)
    if ocorrencia is None:
        aviso = "Preencha o tipo, o recurso e o período afetado (o fim deve ser depois do início)."
        return _avisar(aviso, "/")
    clinica = _clinica()
    if not recurso_combina_com_o_tipo(ocorrencia, clinica.centro):
        return _avisar("O recurso escolhido não corresponde ao tipo de ocorrência.", "/")
    analise = analisar(ocorrencia, clinica.centro)
    if not analise.afetadas:
        return _avisar("Nenhuma cirurgia afetada pela ocorrência.", "/", status=200)
    planos = PLANOS_CANCELAMENTO if request.form.get("acao") == "cancelar" else PLANOS_PADRAO
    clinica.pendente = (analise, gerar_opcoes(analise, planos=planos))
    return _seguir_para("/opcoes")


@rotas.get("/opcoes")
def opcoes():
    clinica = _clinica()
    if clinica.pendente is None:
        return redirect("/")
    analise, lista = clinica.pendente
    return render_template(
        "opcoes.html", analise=analise, opcoes=lista, responsavel=RESPONSAVEL, centro=clinica.centro
    )


@rotas.post("/decisao")
def decisao():
    clinica = _clinica()
    if clinica.pendente is None:
        return redirect("/")
    analise, lista = clinica.pendente
    indice = None if request.form.get("acao") == "rejeitar" else int(request.form["opcao"])
    pedido = PedidoDeDecisao(
        RESPONSAVEL, request.form.get("justificativa", ""), _agora(), "confirmado" in request.form
    )
    try:
        clinica.atualizar(decidir(analise, lista, indice, pedido, clinica.banco))
    except DecisaoInvalida as erro:
        return _avisar(f"{erro}.", "/opcoes")
    clinica.pendente = None
    flash("Programação atualizada. Decisão registrada para auditoria.")
    return _seguir_para("/")
