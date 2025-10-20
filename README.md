# Índices Invertidos (BSBI) y Compresión

Este directorio contiene una implementación educativa del algoritmo BSBI (Blocked Sort-Based Indexing) para construir índices invertidos sobre un corpus de textos, junto con un script interactivo de búsquedas booleanas y una demo de compresión (front coding para el diccionario y Variable-Byte con d-gaps para postings).

## Contenido

- `indexar.py`: Implementación de BSBI.
- `buscar.py`: CLI interactivo para búsquedas (simple, AND, OR, NOT y expresiones booleanas con paréntesis).
- `comprimir.py`: Rutinas de compresión (diccionario con front coding y postings con Variable-Byte + d-gaps).
- `main.py`: Demo end-to-end: construir índice, comprimir, persistir y ejecutar el buscador.
- `smoke_test_comprimido.py`: Test de validación de la compresión/decodificación.
- `corpus/`: Archivos `.txt` de ejemplo para construir el índice.
- `index/`: Directorio donde se persisten los índices comprimidos.

## Requisitos

- Python 3.8+
- No requiere dependencias externas. Opcionalmente puedes instalar el paquete local con el `pyproject.toml` en `contenidos/_static/code/`.

## Uso rápido

### Opción 1: Usando Makefile (recomendado)

```bash
# Construir el índice
make run

# Ejecutar el buscador interactivo
make search
```

### Opción 2: Usando Python directamente

```bash
# 1. Construir y comprimir el índice
python main.py

# 2. Ejecutar el buscador interactivo
python buscar.py
```

**Nota importante:** El buscador (`buscar.py`) requiere que el índice esté construido previamente en `./index/`. Si no existe el índice, se mostrará un mensaje de error indicando que debe ejecutar `make run` o `python main.py` primero.

### Menú de búsqueda

El buscador ofrece las siguientes opciones:

- **0: Buscar una palabra** - Búsqueda simple de un término
- **1: Buscar con AND** - Documentos que contienen TODOS los términos
- **2: Buscar con OR** - Documentos que contienen AL MENOS UNO de los términos
- **3: Buscar con NOT** - Documentos que NO contienen ninguno de los términos
- **4: Consulta booleana** - Expresiones con paréntesis y operadores (AND, OR, NOT)
- **5: Salir**

### Ejemplos de uso

**Búsqueda simple:**

```text
Opción: 0
Palabra: hobbit
→ Documentos que contienen 'hobbit': ['Bombadil', 'Introduccion']
```

**Búsqueda AND:**

```text
Opción: 1
Términos: perro gato
→ Documentos encontrados: ['Bombadil', 'Introduccion', 'Niggle', 'Roverandom']
```

**Consulta booleana:**

```text
Opción: 4
Consulta: (hobbit OR elfo) AND anillo
→ Documentos encontrados: ['Bombadil', 'Introduccion']
```

## Detalles de implementación

### Construcción del índice (BSBI)

- El índice se construye procesando documentos en bloques y fusionándolos con merge de k-vías
- Los términos se normalizan (minúsculas, sin puntuación)
- Los doc_ids se mapean a enteros consecutivos para la compresión

### Compresión

**Diccionario (front coding por bloques):**

- Cada bloque guarda el primer término completo
- Los siguientes términos se comprimen guardando la longitud del prefijo común (LCP) y el sufijo

**Postings (d-gaps + Variable-Byte):**

- Las listas de postings se convierten a d-gaps (diferencias entre IDs consecutivos)
- Cada gap se codifica con Variable-Byte (VB)

### Búsquedas

- El buscador soporta dos backends:
  - **Índice comprimido**: Lee desde `index/` (postings.bin, lexicon.bin, etc.)
  - **BSBI en memoria**: Construye el índice on-the-fly si no existe el comprimido
- Las consultas booleanas se procesan con el algoritmo Shunting Yard (conversión a RPN)
  - Precedencias: `NOT > AND > OR`
  - `NOT` es unario y asociativo a la derecha
- **Los resultados se muestran con nombres de documentos**, no IDs internos

## Estructura de directorios

```text
IndiceInvertido/
├─ README.md
├─ Makefile                # Automatización de tareas
├─ __init__.py
├─ indexar.py              # Construcción del índice (BSBI)
├─ buscar.py               # Interfaz de búsqueda interactiva
├─ comprimir.py            # Algoritmos de compresión
├─ main.py                 # Demo end-to-end
├─ smoke_test_comprimido.py # Validación de compresión
├─ corpus/                 # Documentos de ejemplo
│  ├─ Introduccion.txt
│  ├─ Bombadil.txt
│  ├─ Niggle.txt
│  └─ Roverandom.txt
└─ index/                  # Índice comprimido (generado)
   ├─ postings.bin
   ├─ lexicon.bin
   ├─ postings_offsets.json
   └─ doc_maps.json
```

## Flujo de trabajo con Makefile

```bash
# 1. Ver ayuda
make help

# 2. Construir índice por primera vez
make run

# 3. Ver estadísticas del índice
make stats

# 4. Ejecutar validación
make test

# 5. Limpiar índice anterior y reconstruir
make rebuild

# 6. Solo limpiar archivos generados
make clean
```

## Notas

- **El buscador solo funciona con índice comprimido:** Si se ejecuta `buscar.py` sin índice construido, mostrará un mensaje de error y terminará
- Si se modifica el corpus, reconstruir con `make rebuild` o `python main.py`
- El índice comprimido se guarda en la carpeta `index/`
- Los resultados de búsqueda muestran nombres de documentos (ej: "Bombadil", "Niggle") en lugar de IDs numéricos
- Usar `make clean` antes de reconstruir si se modificó el corpus
