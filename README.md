# Paquete `ii` (Índices Invertidos)

Este directorio contiene una implementación educativa del algoritmo BSBI (Blocked Sort-Based Indexing) para construir índices invertidos sobre un corpus de textos, junto con un script interactivo de búsquedas booleanas.

## Contenido

- `ii.py`: Implementación de BSBI.
- `busquedas.py`: CLI simple para consultas AND, OR, NOT y expresiones con paréntesis.
- `corpus/`: Archivos `.txt` de ejemplo para construir el índice.

## Requisitos

- Python 3.8+
- No requiere dependencias externas. Opcionalmente puedes instalar el paquete local con el `pyproject.toml` en `contenidos/_static/code/`.

## Uso rápido

1. Ejecutar el ejemplo de construcción de índice y búsquedas incluidas en `ii.py`:

```bash
python ii.py
```

2. Usar el buscador interactivo:

```bash
python busquedas.py
```

Menú disponible:

- 1: Búsqueda AND (términos separados por espacios)
- 2: Búsqueda OR (términos separados por espacios)
- 3: Búsqueda NOT (excluye documentos que contengan cualquiera de los términos)
- 4: Consulta booleana con paréntesis ((), AND, OR, NOT)
- 5: Salir

Ejemplo de consulta booleana:

```text
(frodo AND ring) OR (gandalf AND NOT sauron)
```

## Detalles de implementación

- El índice se construye con BSBI procesando documentos en bloques y fusionándolos (merge de k‑vías).
- La búsqueda se hace sobre `bsbi.indice_final`, normalizando términos (minúsculas, sin puntuación).
- El parser booleando convierte la consulta a RPN (Shunting Yard):
  - Precedencias: NOT > AND > OR
  - `NOT` es unario y asociativo a la derecha

## Estructura de directorios

```text
ii/
├─ README.md
├─ ii.py
├─ busquedas.py
└─ corpus/
   ├─ Introduccion.txt
   ├─ ...
```

## Notas

- Si modificas el corpus, vuelve a ejecutar `busquedas.py` para reconstruir el índice.
- Para integrarlo en Jupyter Book, consulta el capítulo `3-9-indices-invertidos.md`, que utiliza `literalinclude` para explicar `ii.py` función por función.
