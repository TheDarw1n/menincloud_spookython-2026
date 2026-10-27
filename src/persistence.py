"""Snapshots y resultados en DynamoDB (tabla manta-snapshots, pk/sk String).
Solo se activa si existe SNAPSHOTS_TABLE. Usa el task role (sin llaves en el codigo).
Timeouts cortos: un DynamoDB lento nunca debe frenar el juego (el simulador guarda en segundo plano)."""
import json
import os
import time


class Snapshots:
    def __init__(self, tabla=None, region=None):
        self.tabla = tabla if tabla is not None else os.environ.get("SNAPSHOTS_TABLE", "")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._t = None

    @property
    def habilitado(self):
        return bool(self.tabla)

    def _table(self):
        if self._t is None:
            import boto3
            from botocore.config import Config
            cfg = Config(connect_timeout=1, read_timeout=1, retries={"max_attempts": 2, "mode": "standard"})
            self._t = boto3.resource("dynamodb", region_name=self.region, config=cfg).Table(self.tabla)
        return self._t

    def preparar(self):
        """Importa boto3 y arma la tabla al arrancar: hacerlo en el primer snapshot (turno 10 de la
        primera ronda) costaba ~1.1 s de CPU a mitad de ronda, compitiendo con /paso."""
        if self.habilitado:
            self._table().meta.client.meta.service_model.operation_model("PutItem")

    def _put(self, pk, sk, texto):
        self._table().put_item(Item={"pk": pk, "sk": sk, "estado": texto, "ttl": int(time.time()) + 7 * 86400})

    def guardar(self, turno, texto):
        """`texto`: el estado ya serializado en JSON (se serializa en el turno, no en el hilo)."""
        if self.habilitado:
            self._put("SNAPSHOT", f"{int(time.time()):012d}-T{turno}", texto)

    def guardar_resultado(self, ronda, texto):
        if self.habilitado:
            self._put("RONDA", f"{int(time.time()):012d}-R{ronda}", texto)

    def ultimo(self):
        if not self.habilitado:
            return None
        r = self._table().query(KeyConditionExpression="pk = :p",
                                ExpressionAttributeValues={":p": "SNAPSHOT"},
                                ScanIndexForward=False, Limit=1)
        return json.loads(r["Items"][0]["estado"]) if r["Items"] else None
