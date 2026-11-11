import io
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asistente import analizar, detectar, normaliza  # noqa: E402


def datos():
    return pd.DataFrame(
        {
            "Pedido": ["A1", "A2", "A2", "A3", "A4", "A5"],
            "Fecha": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-01-20", "2026-02-03", "2026-02-18", "2026-03-10"]),
            "Ciudad": ["Bogotá", "bogota ", "bogota ", "Cali", "Cali", "Cali"],
            "Total venta": [100, 200, 200, 300, 50, 400],
        }
    )


class PruebasAsistente(unittest.TestCase):
    def test_detecta_columnas(self):
        c = detectar(datos())
        self.assertEqual(c["fecha"], "Fecha")
        self.assertEqual(c["medida"], "Total venta")
        self.assertIn("Ciudad", c["categorias"])

    def test_quita_pedidos_repetidos(self):
        r = analizar(datos())
        self.assertEqual(r["duplicados_quitados"], 1)
        self.assertEqual(r["total"], 1050)  # 100 + 200 + 300 + 50 + 400

    def test_detecta_escrituras_distintas(self):
        r = analizar(datos())
        self.assertTrue(any("varias formas" in x["texto"] for x in r["calidad"]))

    def test_normaliza(self):
        self.assertEqual(normaliza(pd.Series([" Bogotá "])).iat[0], "bogota")

    def test_sin_columna_numerica(self):
        r = analizar(pd.DataFrame({"a": ["x", "y"], "b": ["z", "w"]}))
        self.assertIn("No encontré", r["hallazgos"][0])


if __name__ == "__main__":
    unittest.main()
