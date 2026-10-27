import asyncio
import json

from src.simulator.cliente import ClientePaso


def _con_largo(cuerpo):
    return b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: %d\r\n\r\n" % len(cuerpo) + cuerpo


def _chunked(cuerpo):
    return b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n%x\r\n" % len(cuerpo) + cuerpo + b"\r\n0\r\n\r\n"


def _servidor(respuestas, conexiones):
    """Servidor HTTP de juguete: responde en orden las respuestas crudas dadas."""
    vistas = []

    async def atender(r, w):
        conexiones.append(1)
        while respuestas:
            cab = await r.readuntil(b"\r\n\r\n")
            largo = next(int(l.split(b":")[1]) for l in cab.split(b"\r\n") if l.lower().startswith(b"content-length"))
            vistas.append(json.loads(await r.readexactly(largo)))
            w.write(respuestas.pop(0))
            await w.drain()
        w.close()

    return atender, vistas


def test_cliente_reusa_la_conexion_y_lee_content_length_y_chunked():
    async def correr():
        conexiones = []
        atender, vistas = _servidor([_con_largo(b'{"siguienteNodo": "N-0002"}'),
                                     _chunked(b'{"siguienteNodo": "N-0003"}')], conexiones)
        srv = await asyncio.start_server(atender, "127.0.0.1", 0)
        cli = ClientePaso(f"http://127.0.0.1:{srv.sockets[0].getsockname()[1]}", "k", conexiones=4)
        a = await cli.paso("S-1", "N-0001", 1)
        b = await cli.paso("S-1", "N-0002", 2)
        await cli.cerrar()
        srv.close()
        return a, b, vistas, conexiones

    a, b, vistas, conexiones = asyncio.run(correr())
    assert (a, b) == ("N-0002", "N-0003") and len(conexiones) == 1  # una sola conexion reutilizada
    assert vistas == [{"sobrevivienteId": "S-1", "nodoActual": "N-0001", "turno": 1},
                      {"sobrevivienteId": "S-1", "nodoActual": "N-0002", "turno": 2}]


def test_cliente_error_http_lanza_excepcion():
    async def correr():
        atender, _ = _servidor([b"HTTP/1.1 401 Unauthorized\r\ncontent-length: 2\r\n\r\n{}"], [])
        srv = await asyncio.start_server(atender, "127.0.0.1", 0)
        cli = ClientePaso(f"http://127.0.0.1:{srv.sockets[0].getsockname()[1]}", "mala")
        try:
            await cli.paso("S-1", "N-0001", 1)
        except RuntimeError as e:
            return str(e)
        finally:
            await cli.cerrar()
            srv.close()

    assert "401" in asyncio.run(correr())
