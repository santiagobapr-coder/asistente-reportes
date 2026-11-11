"""Crea ejemplo_ventas.xlsx: un Excel 'sucio' como los que mandan los clientes reales."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(3)
fechas = pd.date_range("2026-01-01", "2026-10-20", freq="D")
ciudades = ["Bogotá", "Medellín", "Cali", "Barranquilla"]
productos = ["Camiseta", "Pantalón", "Chaqueta", "Zapatos", "Gorra", "Bolso"]
precio = {"Camiseta": 45000, "Pantalón": 90000, "Chaqueta": 180000, "Zapatos": 150000, "Gorra": 30000, "Bolso": 120000}

rows = []
for d in fechas:
    n = rng.poisson(6 * (1 + 0.003 * (d - fechas[0]).days) * (1.3 if d.month == 5 else 1))
    for _ in range(n):
        p = rng.choice(productos, p=[0.3, 0.2, 0.1, 0.15, 0.15, 0.1])
        ciudad = rng.choice(ciudades, p=[0.5, 0.25, 0.15, 0.10])
        cant = int(rng.choice([1, 2, 3], p=[0.7, 0.2, 0.1]))
        rows.append([d, ciudad, p, cant, precio[p] * cant])
df = pd.DataFrame(rows, columns=["Fecha", "Ciudad", "Producto", "Cantidad", "Total venta"])
df.insert(0, "Pedido", [f"PED-{i:05d}" for i in range(1, len(df) + 1)])

# Suciedad típica
df.loc[rng.choice(len(df), 40, replace=False), "Ciudad"] = "bogota "          # variantes de escritura
df.loc[rng.choice(len(df), 25, replace=False), "Ciudad"] = "MEDELLIN"
df.loc[rng.choice(len(df), 60, replace=False), "Producto"] = np.nan            # vacíos
df = pd.concat([df, df.sample(30, random_state=1)])                              # duplicados
df.loc[df.sample(3, random_state=5).index[0], "Total venta"] = 4_800_000       # valor atípico
df = df.sort_values("Fecha").reset_index(drop=True)
df.to_excel("ejemplo_ventas.xlsx", index=False)
print(len(df), "filas")
