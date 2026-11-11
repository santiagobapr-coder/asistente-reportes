# Asistente de reportes

Sube un Excel o CSV de ventas y recibe un **informe en lenguaje claro**: cómo va la tendencia,
qué categorías pesan más, qué datos se ven raros y qué hay que corregir antes de confiar en los totales.
Pensado para dueños de negocio que reciben archivos desordenados y no quieren armar el análisis a mano.

## Qué hace

1. **Detecta solo** las columnas de fecha, de valor (ventas, total, monto…) y de categorías.
2. **Calcula:** total, comparación del último mes completo contra el anterior, mejor y peor mes,
   día de la semana más fuerte, concentración por categoría (ciudad, producto…).
3. **Revisa la calidad:** pedidos repetidos, celdas vacías, categorías escritas de varias formas
   («Bogotá» / «bogota »), valores negativos y registros muy fuera de lo normal.
4. **Escribe el resumen y los próximos pasos** en español sencillo.

## Uso

```bash
pip install -r requirements.txt

# Opción 1: por línea de comandos
python asistente.py ejemplo_ventas.xlsx          # crea informe.html

# Opción 2: una página local para subir archivos
python asistente.py --servir                      # abre http://localhost:8000
```

El archivo se procesa en el computador del usuario y no se guarda.

## Resumen redactado con IA (opcional)

El análisis funciona sin IA. Si defines `ANTHROPIC_API_KEY`, se agrega un párrafo redactado por un modelo
de lenguaje a partir de las cifras ya calculadas (**no se envían las filas del archivo**). Puedes elegir el
modelo con `ASISTENTE_MODELO`. Si no hay clave o falla la conexión, se usa el resumen local.

> Esta parte usa una llamada de red a la API y no la pude probar en el entorno donde construí el proyecto;
> el resto (análisis, informe y servidor local) sí está probado.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Archivos

| Archivo | Descripción |
| --- | --- |
| `asistente.py` | Lectura, detección de columnas, análisis, informe y servidor local |
| `generate_example.py` | Crea `ejemplo_ventas.xlsx`, un Excel con problemas típicos (duplicados, vacíos, variantes de escritura, un valor atípico) |
| `dashboard_kit.py` | Diseño del informe |
| `tests/` | Pruebas del análisis |

## Límites actuales

- Pensado para tablas planas (una fila por venta o movimiento), no para hojas con varias tablas.
- Elige una sola columna de valor; si el archivo tiene varias, usa la que parece ventas o total.

## Tecnologías

Python, pandas, matplotlib, openpyxl, biblioteca estándar (`http.server`).


## Qué busca (el problema)

Archivos de Excel desordenados que nadie tiene tiempo de revisar.

## Cómo se cumple

Lee un Excel, detecta columnas, revisa calidad (duplicados, vacíos, atípicos) y genera un informe en lenguaje claro; resumen con IA opcional (sin probar).

## Cómo ofrecerlo como servicio

- **Qué entrego:** Herramienta instalada para tu equipo o informes por encargo.
- **A quién:** Equipos administrativos y comerciales que reciben archivos de varias fuentes.
- **Precio de referencia (ajustar):** Por informe: 100.000–300.000 COP. Instalación a medida: 600.000–1.500.000 COP.
- **Frase para empezar:** «Mándame tu Excel y te devuelvo un informe claro y las alertas de calidad de datos.»
- **Flujo:** 1) reunión corta y datos del cliente → 2) prototipo con sus datos → 3) ajustes → 4) entrega y capacitación.

> Datos del repositorio inventados; ejecutar los scripts para reproducir el tablero.
