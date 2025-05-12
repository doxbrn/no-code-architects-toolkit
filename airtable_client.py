import os
import requests
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AirtableClient:
    """
    Cliente para interagir com a API do Airtable,
    permitindo listar tabelas e buscar registros.
    """

    def __init__(self):
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_id = os.getenv("AIRTABLE_BASE_ID")
        self.base_url = "https://api.airtable.com"
        if not self.api_key or not self.base_id:
            raise ValueError("Configure as variáveis AIRTABLE_API_KEY e AIRTABLE_BASE_ID")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def list_tables(self) -> List[str]:
        """
        Lista todos os nomes de tabelas da base usando o endpoint de metadados.
        Atenção: seu API Key precisa ter acesso ao Metadata API.
        """
        url = f"{self.base_url}/v0/meta/bases/{self.base_id}/tables"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        tables = [tbl["name"] for tbl in data.get("tables", [])]
        logger.info(f"Tabelas encontradas: {tables}")
        return tables

    def get_all_records(
        self,
        table_name: str,
        view: Optional[str] = None,
        page_size: int = 100
    ) -> List[Dict]:
        """
        Busca todos os registros de uma tabela, fazendo paginação.
        :param table_name: nome exato da tabela
        :param view: (opcional) nome da view para filtrar/registros
        :param page_size: máximo por página (até 100)
        """
        records = []
        offset = None
        url = f"{self.base_url}/v0/{self.base_id}/{table_name}"

        params = {
            "pageSize": page_size
        }
        if view:
            params["view"] = view

        while True:
            if offset:
                params["offset"] = offset

            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            payload = resp.json()
            records.extend(payload.get("records", []))

            offset = payload.get("offset")
            if not offset:
                break

        logger.info(f"{len(records)} registros obtidos da tabela '{table_name}'")
        return records


if __name__ == "__main__":
    # Exemplo de uso
    client = AirtableClient()

    # 1) Listar tabelas
    try:
        tables = client.list_tables()
    except requests.HTTPError as e:
        logger.error("Falha ao listar tabelas: %s", e)
        tables = []

    # 2) Para cada tabela, buscar e imprimir os registros
    for tbl in tables:
        try:
            recs = client.get_all_records(tbl)
            print(f"\n=== Tabela: {tbl} ({len(recs)} registros) ===")
            for r in recs:
                # Cada 'r' tem chaves: 'id' e 'fields'
                print(f"- {r['id']}: {r['fields']}")
        except requests.HTTPError as e:
            logger.error("Erro ao buscar registros da '%s': %s", tbl, e) 