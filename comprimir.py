"""
Compresión de índices invertidos: Front Coding para el diccionario de términos
y Variable-Byte (VB) con d-gaps para las listas de postings.

Este módulo está pensado para funcionar con el índice producido por indexar.py
(clase BSBI). La función principal es `comprimir_indice`.

Notas (alineado al apunte teórico):
- Diccionario: front coding bloqueado. En cada bloque se guarda el primer
  término completo y para los siguientes se guarda la longitud del prefijo
  común con el primero del bloque (LCP) y el sufijo restante.
- Postings: se comprimen en un blob único aplicando d-gaps y luego
  codificación Variable-Byte por cada gap.

Estructura de retorno de `comprimir_indice`:
{
  'lexicon_bytes': bytes,               # diccionario comprimido
  'lexicon_block_size': int,            # tamaño de bloque usado para FC
  'lexicon_terms_order': list[str],     # términos en orden (para referencia)
  'postings_bytes': bytes,              # blob con todas las postings VB
  'postings_offsets': dict[str, (int,int)],  # term -> (offset, length)
  'doc_id_map': dict[str,int],          # mapeo doc_id original -> entero
  'rev_doc_id_map': list[str],          # índice a doc_id original
}

Incluye funciones `vb_encode_number`, `vb_encode_list`, y utilidades para
front coding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable


# =============== Variable-Byte (VB) encoding ===============


def vb_encode_number(n: int) -> bytes:
    """Codifica un entero no negativo con Variable-Byte.

    Regla estándar: se parte en base-128. Se marcan todos los bytes con el bit
    más significativo MSB=0, excepto el último byte que finaliza el número con
    MSB=1. El payload en cada byte son los 7 bits inferiores.
    """
    if n < 0:
        raise ValueError("vb_encode_number requiere enteros no negativos")
    chunks: List[int] = []  # de menor a mayor peso (LSB primero)
    while True:
        chunks.append(n % 128)
        n //= 128
        if n == 0:
            break
    # Emitimos de mayor a menor peso; el último emitido lleva MSB=1
    out = bytearray()
    for i in range(len(chunks) - 1, -1, -1):
        b = chunks[i]
        if i == 0:
            b |= 0x80  # marcar último byte
        out.append(b)
    return bytes(out)


def vb_encode_list(nums: Iterable[int]) -> bytes:
    """Codifica una lista de enteros no negativos con VB concatenados."""
    out = bytearray()
    for n in nums:
        out.extend(vb_encode_number(n))
    return bytes(out)


def d_gaps(sorted_docids: List[int]) -> List[int]:
    """Convierte una lista ordenada de docIDs a d-gaps: [d1, d2-d1, ...]."""
    if not sorted_docids:
        return []
    gaps = [sorted_docids[0]]
    for i in range(1, len(sorted_docids)):
        gaps.append(sorted_docids[i] - sorted_docids[i - 1])
    return gaps


# =============== Front coding (bloques) ===============


def lcp(a: str, b: str) -> int:
    """Longest Common Prefix length entre a y b."""
    i = 0
    m = min(len(a), len(b))
    while i < m and a[i] == b[i]:
        i += 1
    return i


def front_code_blocks(terms_sorted: List[str], block_size: int = 8) -> bytes:
    """Serializa el diccionario aplicando front coding por bloques.

    Formato por bloque (bytes):
    - VB(len(base)), base.encode('utf-8')
    - VB(k-1)  donde k es el tamaño del bloque real (<= block_size)
    - Por cada término adicional t en el bloque:
      VB(lcp(base, t)), VB(len(sufijo)), sufijo.encode('utf-8')

    Devolvemos un único blob de bytes con la concatenación de todos los
    bloques.
    """
    out = bytearray()
    n = len(terms_sorted)
    i = 0
    while i < n:
        block = terms_sorted[i : i + block_size]
        base = block[0]
        base_b = base.encode("utf-8")
        out.extend(vb_encode_number(len(base_b)))
        out.extend(base_b)

        followers = block[1:]
        out.extend(vb_encode_number(len(followers)))
        for t in followers:
            p = lcp(base, t)
            suf = t[p:]
            suf_b = suf.encode("utf-8")
            out.extend(vb_encode_number(p))
            out.extend(vb_encode_number(len(suf_b)))
            out.extend(suf_b)
        i += len(block)
    return bytes(out)


# =============== Compresor principal ===============


@dataclass
class CompressedIndex:
    lexicon_bytes: bytes
    lexicon_block_size: int
    lexicon_terms_order: List[str]
    postings_bytes: bytes
    postings_offsets: Dict[str, Tuple[int, int]]
    doc_id_map: Dict[str, int]
    rev_doc_id_map: List[str]


def _normalize_docids_to_ints(
    index: Dict[str, List[object]],
) -> Tuple[Dict[str, List[int]], Dict[str, int], List[str]]:
    """Normaliza los doc_ids (posibles strings) a enteros consecutivos.

    - Si ya son ints, simplemente se asegura de ordenarlos en cada posting.
    - Si son strings, mapea cada doc_id distinto a un entero estable
      determinado por el orden lexicográfico del doc_id original.

    Devuelve: (index_int, doc_id_map, rev_doc_id_map)
    """
    # Recolectar todos los doc_ids
    all_docids = set()
    example = None
    for plist in index.values():
        if plist:
            example = plist[0]
        for d in plist:
            all_docids.add(d)

    if example is None:
        # índice vacío
        return {t: [] for t in index.keys()}, {}, []

    # Determinar si son ints
    are_ints = isinstance(example, int)
    if are_ints:
        # Convertimos a int por las dudas (si vienen como str de números)
        def to_int(x):
            return int(x)

        doc_id_map = {str(x): int(x) for x in sorted(set(map(int, all_docids)))}
        rev = [None] * (max(doc_id_map.values()) + 1)
        for s, i in doc_id_map.items():
            rev[i] = s
    else:
        # Mapear strings a enteros consecutivos estables
        sorted_ids = sorted(map(str, all_docids))
        doc_id_map = {doc: i for i, doc in enumerate(sorted_ids, start=1)}
        rev = ["<NULL>"] * (len(doc_id_map) + 1)
        for doc, i in doc_id_map.items():
            rev[i] = doc

        def to_int(x):
            # x puede venir como str o cualquier objeto representable
            return doc_id_map[str(x)]

    index_int: Dict[str, List[int]] = {}
    for term, plist in index.items():
        ints = sorted({to_int(d) for d in plist})
        index_int[term] = ints

    return index_int, doc_id_map, rev


def comprimir_indice(
    index: Dict[str, List[object]], block_size: int = 8
) -> CompressedIndex:
    """Comprime un índice invertido (término -> [doc_ids]) con:
    - Front Coding bloqueado para el diccionario de términos
    - d-gaps + Variable-Byte para las listas de postings

    Args:
        index: diccionario {término: lista de doc_ids (str o int)}
        block_size: tamaño de bloque para front coding.

    Returns:
        CompressedIndex con los blobs y metadatos necesarios.
    """
    # 1) Asegurar docIDs enteros ordenados
    index_int, doc_id_map, rev_doc_id_map = _normalize_docids_to_ints(index)

    # 2) Construir blob de postings con VB + d-gaps y offsets por término
    postings_blob = bytearray()
    postings_offsets: Dict[str, Tuple[int, int]] = {}
    # Ordenamos términos para estabilidad y para el diccionario
    terms_sorted = sorted(index_int.keys())

    for term in terms_sorted:
        plist = index_int[term]
        gaps = d_gaps(plist)
        encoded = vb_encode_list(gaps)
        start = len(postings_blob)
        postings_blob.extend(encoded)
        end = len(postings_blob)
        postings_offsets[term] = (start, end - start)

    # 3) Front coding para el diccionario
    lexicon_bytes = front_code_blocks(terms_sorted, block_size=block_size)

    return CompressedIndex(
        lexicon_bytes=bytes(lexicon_bytes),
        lexicon_block_size=block_size,
        lexicon_terms_order=terms_sorted,
        postings_bytes=bytes(postings_blob),
        postings_offsets=postings_offsets,
        doc_id_map=doc_id_map,
        rev_doc_id_map=rev_doc_id_map,
    )


# Nota: si se desea una demo ejecutable, crear un script separado que importe
# este módulo y `indexar.BSBI`, para evitar dependencias implícitas aquí.
