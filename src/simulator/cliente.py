"""Cliente HTTP/1.1 minimo para POST /paso con conexiones persistentes.

El simulador hace cientos de consultas por turno desde el MISMO proceso (y event loop) que el
servidor: con httpx el cliente gastaba mas CPU que el propio /paso y la latencia medida se inflaba
hasta los 500 ms. Este cliente solo escribe la peticion y lee la respuesta (Content-Length o
chunked), reutilizando un pool de sockets. Si una consulta se cancela (timeout de 500 ms) su
conexion se cierra para no desincronizar el socket."""
import asyncio
import json
import ssl
from urllib.parse import urlsplit


class ClientePaso:
    def __init__(self, url, api_key, conexiones=48):
        u = urlsplit(url)
        self.host = u.hostname
        self.tls = ssl.create_default_context() if u.scheme == "https" else None
        self.port = u.port or (443 if self.tls else 80)
        self.cabecera = (f"POST /paso HTTP/1.1\r\nHost: {u.netloc}\r\nx-api-key: {api_key}\r\n"
                         "Content-Type: application/json\r\n").encode()
        self.max = conexiones
        self.abiertas = 0
        self.libres = asyncio.Queue()

    async def _tomar(self):
        if not self.libres.empty():
            return self.libres.get_nowait()
        if self.abiertas < self.max:
            self.abiertas += 1
            try:
                return await asyncio.open_connection(self.host, self.port, ssl=self.tls)
            except BaseException:
                self.abiertas -= 1
                raise
        return await self.libres.get()

    async def _leer(self, r):
        estado = int((await r.readline()).split()[1])
        largo, chunked, cerrar = 0, False, False
        while True:
            linea = await r.readline()
            if linea in (b"\r\n", b""):
                break
            k, _, v = linea.partition(b":")
            k, v = k.strip().lower(), v.strip().lower()
            if k == b"content-length":
                largo = int(v)
            elif k == b"transfer-encoding" and b"chunked" in v:
                chunked = True
            elif k == b"connection" and v == b"close":
                cerrar = True
        if not chunked:
            return estado, await r.readexactly(largo), cerrar
        partes = []
        while True:
            n = int((await r.readline()).split(b";")[0], 16)
            if n == 0:
                await r.readline()
                return estado, b"".join(partes), cerrar
            partes.append(await r.readexactly(n))
            await r.readline()

    async def paso(self, sid, nodo, turno):
        cuerpo = json.dumps({"sobrevivienteId": sid, "nodoActual": nodo, "turno": turno}).encode()
        r, w = await self._tomar()
        reusar = False
        try:
            w.write(self.cabecera + b"Content-Length: %d\r\n\r\n" % len(cuerpo) + cuerpo)
            estado, datos, cerrar = await self._leer(r)
            reusar = not cerrar
        finally:
            if reusar:
                self.libres.put_nowait((r, w))
            else:
                self.abiertas -= 1
                w.close()
        if estado != 200:
            raise RuntimeError(f"/paso respondio {estado}")
        return json.loads(datos)["siguienteNodo"]

    async def cerrar(self):
        while not self.libres.empty():
            _, w = self.libres.get_nowait()
            w.close()
        self.abiertas = 0
