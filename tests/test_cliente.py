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


def _puerto(srv):
    return srv.sockets[0].getsockname()[1]


def test_cliente_descarta_la_conexion_que_el_servidor_cerro_por_inactividad():
    async def correr():
        conexiones = []

        async def atender(r, w):  # responde UNA consulta y cierra, como un keep-alive vencido
            conexiones.append(1)
            cab = await r.readuntil(b"\r\n\r\n")
            await r.readexactly(int(cab.lower().split(b"content-length:")[1].split(b"\r\n")[0]))
            w.write(_con_largo(b'{"siguienteNodo": "N-0002"}'))
            await w.drain()
            w.close()

        srv = await asyncio.start_server(atender, "127.0.0.1", 0)
        cli = ClientePaso(f"http://127.0.0.1:{_puerto(srv)}", "k")
        a = await cli.paso("S-1", "N-0001", 1)
        await asyncio.sleep(0.1)  # el cierre llega mientras la conexion esta libre en el pool
        b = await cli.paso("S-1", "N-0001", 2)
        await cli.cerrar()
        srv.close()
        return a, b, len(conexiones)

    assert asyncio.run(correr()) == ("N-0002", "N-0002", 2)


def test_cliente_reintenta_una_vez_si_la_conexion_reusada_se_cierra_al_enviar():
    async def correr():
        conexiones = []

        async def atender(r, w):  # 1a conexion: responde una y cierra al leer la segunda sin responder
            conexiones.append(1)
            n = 0
            while True:
                cab = await r.readuntil(b"\r\n\r\n")
                await r.readexactly(int(cab.lower().split(b"content-length:")[1].split(b"\r\n")[0]))
                n += 1
                if len(conexiones) == 1 and n == 2:
                    w.close()
                    return
                w.write(_con_largo(b'{"siguienteNodo": "N-0003"}'))
                await w.drain()

        srv = await asyncio.start_server(atender, "127.0.0.1", 0)
        cli = ClientePaso(f"http://127.0.0.1:{_puerto(srv)}", "k")
        a = await cli.paso("S-1", "N-0001", 1)
        b = await cli.paso("S-1", "N-0001", 2)
        await cli.cerrar()
        srv.close()
        return a, b, len(conexiones)

    assert asyncio.run(correr()) == ("N-0003", "N-0003", 2)


def test_cliente_manda_el_secreto_de_origen():
    async def correr():
        vistas = []

        async def atender(r, w):
            cab = await r.readuntil(b"\r\n\r\n")
            vistas.append(cab.lower())
            await r.readexactly(int(cab.lower().split(b"content-length:")[1].split(b"\r\n")[0]))
            w.write(_con_largo(b'{"siguienteNodo": "N-0002"}'))
            await w.drain()

        srv = await asyncio.start_server(atender, "127.0.0.1", 0)
        for origen in ("abc", ""):
            cli = ClientePaso(f"http://127.0.0.1:{_puerto(srv)}", "k", origen=origen)
            await cli.paso("S-1", "N-0001", 1)
            await cli.cerrar()
        srv.close()
        return vistas

    con, sin = asyncio.run(correr())
    assert b"x-origin-verify: abc\r\n" in con and b"x-origin-verify" not in sin


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
