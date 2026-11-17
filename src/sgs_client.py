from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SGSClient:
    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

    def __init__(self, max_retries: int = 5, backoff_factor: float = 1.5):
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Databricks-SGS-Connector/1.0"
        })

    def _gerar_janelas_datas(self, data_inicial: str, data_final: str, anos_janela: int = 5):
        """Divide o intervalo em janelas menores para evitar o erro de limite de 10 anos do BACEN."""
        dt_ini = datetime.strptime(data_inicial, "%d/%m/%Y")
        dt_fim = datetime.strptime(data_final, "%d/%m/%Y")

        janelas = []
        atual_ini = dt_ini
        while atual_ini <= dt_fim:
            atual_fim = min(atual_ini + relativedelta(years=anos_janela) - relativedelta(days=1), dt_fim)
            janelas.append((atual_ini.strftime("%d/%m/%Y"), atual_fim.strftime("%d/%m/%Y")))
            atual_ini = atual_fim + relativedelta(days=1)
        return janelas

    def extrair_serie(self, codigo: int, data_inicial: str, data_final: str) -> list[dict]:
        """Extrai os dados de uma série do SGS paginando por janelas de tempo."""
        janelas = self._gerar_janelas_datas(data_inicial, data_final)
        dados_completos = []

        for ini, fim in janelas:
            url = self.BASE_URL.format(codigo=codigo)
            params = {
                "formato": "json",
                "dataInicial": ini,
                "dataFinal": fim
            }
            logger.info(f"Extraindo série {codigo} no período de {ini} até {fim}...")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            lote = response.json()
            if isinstance(lote, list):
                dados_completos.extend(lote)

        return dados_completos