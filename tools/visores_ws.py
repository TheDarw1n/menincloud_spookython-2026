"""Visores del mapa para la prueba de carga: abre N WebSocket a /ws y cuenta los estados recibidos.
Ofrecen compresion como un navegador (el servidor la rechaza: ver Dockerfile).

  python tools/visores_ws.py ws://127.0.0.1:8000/ws 30 55   (30 visores durante 55 s)"""
import asyncio
import sys
import time

import websockets


async def visor(url, hasta, recibidos):
    async with websockets.connect(url, max_size=None) as ws:
        while (falta := hasta - time.monotonic()) > 0:
            try:
                await asyncio.wait_for(ws.recv(), timeout=falta)
            except asyncio.TimeoutError:
                break
            recibidos[0] += 1


async def main(url, n, segundos):
    hasta, recibidos = time.monotonic() + segundos, [0]
    res = await asyncio.gather(*(visor(url, hasta, recibidos) for _ in range(n)), return_exceptions=True)
    fallidos = sum(isinstance(r, Exception) for r in res)
    print(f"{n} visores WebSocket x {segundos:.0f} s: {recibidos[0]} estados recibidos, "
          f"{fallidos} conexiones fallidas")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2]), float(sys.argv[3])))
