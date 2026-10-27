"""Snapshots y resultados en DynamoDB (tabla manta-snapshots, pk/sk String).
Solo se activa si existe SNAPSHOTS_TABLE. Usa el task role (sin llaves en el codigo)."""
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
            self._t = boto3.resource("dynamodb", region_name=self.region).Table(self.tabla)
        return self._t

    def _put(self, pk, sk, datos):
        self._table().put_item(Item={"pk": pk, "sk": sk, "estado": json.dumps(datos),
                                     "ttl": int(time.time()) + 7 * 86400})

    def guardar(self, turno, datos):
        if self.habilitado:
            self._put("SNAPSHOT", f"{int(time.time()):012d}-T{turno}", datos)

    def guardar_resultado(self, ronda, datos):
        if self.habilitado:
            self._put("RONDA", f"{int(time.time()):012d}-R{ronda}", datos)

    def ultimo(self):
        if not self.habilitado:
            return None
        r = self._table().query(KeyConditionExpression="pk = :p",
                                ExpressionAttributeValues={":p": "SNAPSHOT"},
                                ScanIndexForward=False, Limit=1)
        return json.loads(r["Items"][0]["estado"]) if r["Items"] else None
