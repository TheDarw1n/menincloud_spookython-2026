import os

# Los tests usan un grafo fijo de 20 nodos (cuadricula 4x5) para que las aserciones no
# dependan del export real de Manta (data/manta_graph.json). Se fija antes de importar src.api.
GRAFO_PRUEBA = os.path.join(os.path.dirname(__file__), "data", "grafo_prueba.json")
os.environ["GRAPH_PATH"] = GRAFO_PRUEBA
os.environ.setdefault("API_KEY", "test-key")
