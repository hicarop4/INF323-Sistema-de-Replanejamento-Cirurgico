import pytest

from ccreplan.dados_exemplo import centro_de_exemplo
from ccreplan.persistencia import BancoDeDados
from ccreplan.web.app import create_app
from tests.apoio_web import AGORA, DIA


@pytest.fixture
def cliente(tmp_path):
    app = create_app(
        centro_de_exemplo(DIA),
        relogio=lambda: AGORA,
        banco=BancoDeDados(tmp_path / "teste.sqlite3"),
    )
    app.config["TESTING"] = True
    return app.test_client()
