from pathlib import Path
import json
from typing import Dict, List, Tuple, Iterable


# ==== Decodificación Variable-Byte y utilidades ====


def _vb_decode_stream(data: bytes) -> List[int]:
    """Decodifica una secuencia de enteros codificados con VB."""
    nums: List[int] = []
    n = 0
    for b in data:
        if b & 0x80:  # byte final
            n = (n << 7) | (b & 0x7F)
            nums.append(n)
            n = 0
        else:
            n = (n << 7) | b
    if n != 0:
        pass
    return nums


def _from_dgaps(gaps: Iterable[int]) -> List[int]:
    out: List[int] = []
    acc = 0
    for g in gaps:
        acc += g
        out.append(acc)
    return out


class CompressedReader:
    def __init__(self, base_dir: Path):
        self.idx_dir = base_dir / "index"
        self.postings_path = self.idx_dir / "postings.bin"
        self.offsets_path = self.idx_dir / "postings_offsets.json"
        self.maps_path = self.idx_dir / "doc_maps.json"
        self.lexicon_path = self.idx_dir / "lexicon.bin"

        have_all = (
            self.postings_path.exists()
            and self.offsets_path.exists()
            and self.maps_path.exists()
        )
        if not have_all:
            raise FileNotFoundError(
                "Índice comprimido incompleto: faltan archivos en index/"
            )

        self._postings_blob = self.postings_path.read_bytes()
        with open(self.offsets_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            self.offsets: Dict[str, Tuple[int, int]] = {
                k: (int(v[0]), int(v[1])) for k, v in raw.items()
            }
        with open(self.maps_path, "r", encoding="utf-8") as f:
            maps = json.load(f)
            self.rev_doc_id_map: List[str] = maps.get("rev_doc_id_map", [])
            self.doc_id_map: Dict[str, int] = maps.get("doc_id_map", {})
            self.terms_order: List[str] = maps.get("terms_order", [])
            self.block_size: int = int(maps.get("block_size", 8))

        if not self.terms_order and self.lexicon_path.exists():
            # Reconstruir terms_order desde lexicon.bin (front coding)
            self.terms_order = self._decode_lexicon_fc(
                self.lexicon_path.read_bytes(), self.block_size
            )

    @staticmethod
    def _vb_decode_number_from(data: bytes, pos: int) -> Tuple[int, int]:
        """Decodifica un número VB desde data[pos:].

        Retorna (valor, nueva_pos).
        """
        n = 0
        while pos < len(data):
            b = data[pos]
            pos += 1
            if b & 0x80:
                n = (n << 7) | (b & 0x7F)
                return n, pos
            else:
                n = (n << 7) | b
        raise ValueError("VB mal formado: fin de datos")

    @classmethod
    def _decode_lexicon_fc(cls, blob: bytes, _block_size: int) -> List[str]:
        """Decodifica el lexicón front-coded por bloques.

        Retorna la lista de términos. Formato por bloque:
        - VB(len(base)), base
        - VB(k) donde k = cantidad de followers en el bloque
        - Por cada follower: VB(lcp), VB(len_suf), sufijo
        """
        terms: List[str] = []
        pos = 0
        n = len(blob)
        while pos < n:
            # Base term
            base_len, pos = cls._vb_decode_number_from(blob, pos)
            base = blob[pos : pos + base_len].decode("utf-8")
            pos += base_len
            terms.append(base)

            # Followers
            followers, pos = cls._vb_decode_number_from(blob, pos)
            for _ in range(followers):
                lcp_len, pos = cls._vb_decode_number_from(blob, pos)
                suf_len, pos = cls._vb_decode_number_from(blob, pos)
                suf = blob[pos : pos + suf_len].decode("utf-8")
                pos += suf_len
                terms.append(base[:lcp_len] + suf)
        return terms

    def postings(self, term: str) -> List[int]:
        off = self.offsets.get(term)
        if not off:
            return []
        start, length = off
        slice_bytes = self._postings_blob[start : start + length]
        gaps = _vb_decode_stream(slice_bytes)
        return _from_dgaps(gaps)

    def get_doc_name(self, doc_id: int) -> str:
        """Convierte un doc_id (int) a su nombre original."""
        if self.rev_doc_id_map and 0 <= doc_id < len(self.rev_doc_id_map):
            return self.rev_doc_id_map[doc_id]
        return str(doc_id)


# ==== Buscador con backend configurable (BSBI o Comprimido) ====


def mostrar_menu():
    print("\n=== Búsqueda en Índice Invertido ===")
    print(
        "Algunas palabras para probar: "
        "hobbit, anillo, elfo, mago, gato, perro, ratón"
    )
    print("0. Buscar una palabra")
    print("1. Buscar con AND")
    print("2. Buscar con OR")
    print("3. Buscar con NOT")
    print("4. Consulta booleana ((), AND, OR, NOT)")
    print("5. Salir")


def obtener_consulta():
    consulta = input("Ingrese términos de búsqueda separados por espacios: ")
    return consulta.strip().split()


def obtener_palabra_simple():
    return input("Ingrese una palabra a buscar: ").strip()


def obtener_consulta_booleana():
    return input(
        "Ingrese una consulta booleana (use AND, OR, NOT y paréntesis): "
    ).strip()


def _tokenizar_booleana(consulta: str):
    import re

    patron = r"\(|\)|\bAND\b|\bOR\b|\bNOT\b|\w+"
    tokens = []
    for m in re.finditer(patron, consulta, flags=re.IGNORECASE):
        tok = m.group(0)
        up = tok.upper()
        if up in {"AND", "OR", "NOT"}:
            tokens.append(up)
        elif tok in ("(", ")"):
            tokens.append(tok)
        else:
            tokens.append(tok)
    return tokens


def _a_rpn(tokens):
    precedencia = {"OR": 1, "AND": 2, "NOT": 3}
    asociatividad = {"OR": "left", "AND": "left", "NOT": "right"}
    salida = []
    ops = []

    def es_operador(t):
        return t in ("AND", "OR", "NOT")

    for t in tokens:
        if t == "(":
            ops.append(t)
        elif t == ")":
            while ops and ops[-1] != "(":
                salida.append(ops.pop())
            if not ops:
                raise ValueError("Paréntesis desbalanceados")
            ops.pop()
        elif es_operador(t):
            while (
                ops
                and es_operador(ops[-1])
                and (
                    (
                        asociatividad[t] == "left"
                        and precedencia[t] <= precedencia[ops[-1]]
                    )
                    or (
                        asociatividad[t] == "right"
                        and precedencia[t] < precedencia[ops[-1]]
                    )
                )
            ):
                salida.append(ops.pop())
            ops.append(t)
        else:
            salida.append(("TERM", t))

    while ops:
        top = ops.pop()
        if top in ("(", ")"):
            raise ValueError("Paréntesis desbalanceados")
        salida.append(top)

    return salida


def _universo_docs_from_backend(buscar_fn) -> set:
    u = set()
    terms = []
    if hasattr(buscar_fn, "__self__") and hasattr(buscar_fn.__self__, "terms_order"):
        terms = buscar_fn.__self__.terms_order  # type: ignore[attr-defined]
    for t in terms:
        u.update(buscar_fn(t))
    return u


def evaluar_rpn(rpn, buscar_fn, universo: set):
    pila = []
    for t in rpn:
        if isinstance(t, tuple) and t and t[0] == "TERM":
            term = t[1]
            pila.append(set(buscar_fn(term)))
        elif t == "NOT":
            if not pila:
                raise ValueError("Operador NOT sin operando")
            a = pila.pop()
            pila.append(universo - a)
        elif t in ("AND", "OR"):
            if len(pila) < 2:
                raise ValueError(f"Operador {t} con operandos insuficientes")
            b = pila.pop()
            a = pila.pop()
            pila.append(a & b if t == "AND" else a | b)
        else:
            raise ValueError(f"Token desconocido en RPN: {t}")
    if len(pila) != 1:
        raise ValueError("Expresión inválida")
    return pila[0]


def busqueda_and(buscar_fn, terminos):
    sets = [set(buscar_fn(term)) for term in terminos if term]
    return set.intersection(*sets) if sets else set()


def busqueda_or(buscar_fn, terminos):
    sets = [set(buscar_fn(term)) for term in terminos if term]
    return set.union(*sets) if sets else set()


def busqueda_not(buscar_fn, terminos, universo: set):
    sets = [set(buscar_fn(term)) for term in terminos if term]
    excluidos = set.union(*sets) if sets else set()
    return universo - excluidos


def ids_a_nombres(doc_ids: set, doc_name_fn) -> List[str]:
    """Convierte un conjunto de doc_ids a nombres de documentos."""
    nombres = []
    for doc_id in doc_ids:
        if callable(doc_name_fn):
            nombres.append(doc_name_fn(doc_id))
        else:
            nombres.append(str(doc_id))
    return sorted(nombres)


def main():
    base_dir = Path(__file__).parent
    
    try:
        cr = CompressedReader(base_dir)
        buscar_fn = cr.postings
        doc_name_fn = cr.get_doc_name
        universo = _universo_docs_from_backend(buscar_fn)
        if not universo:
            back_desc = "Índice comprimido (NOT limitado)"
        else:
            back_desc = "Índice comprimido"
    except FileNotFoundError:
        print("=" * 60)
        print("ERROR: No se encontró el índice comprimido.")
        print("=" * 60)
        print("\nPor favor, construya el índice primero ejecutando:")
        print("  make run")
        print("  O bien: python main.py")
        print("\nEsto construirá y comprimirá el índice en ./index/")
        print("=" * 60)
        return

    print(f"Backend de búsqueda: {back_desc}")

    while True:
        mostrar_menu()
        opcion = input("Seleccione una opción: ").strip()
        if opcion == "0":
            palabra = obtener_palabra_simple()
            if palabra:
                resultado = set(buscar_fn(palabra))
                nombres = ids_a_nombres(resultado, doc_name_fn)
                print(f"\nDocumentos que contienen '{palabra}':", nombres)
            else:
                print("Debe ingresar una palabra.")
        elif opcion == "1":
            terminos = obtener_consulta()
            resultado = busqueda_and(buscar_fn, terminos)
            nombres = ids_a_nombres(resultado, doc_name_fn)
            print("\nDocumentos encontrados:", nombres)
        elif opcion == "2":
            terminos = obtener_consulta()
            resultado = busqueda_or(buscar_fn, terminos)
            nombres = ids_a_nombres(resultado, doc_name_fn)
            print("\nDocumentos encontrados:", nombres)
        elif opcion == "3":
            terminos = obtener_consulta()
            if universo:
                resultado = busqueda_not(buscar_fn, terminos, universo)
                nombres = ids_a_nombres(resultado, doc_name_fn)
            else:
                print("NOT no disponible en este backend (universo desconocido)")
                nombres = []
            print("\nDocumentos encontrados:", nombres)
        elif opcion == "4":
            print("\nEjemplo de consulta booleana: (gato OR perro) AND NOT ratón")
            try:
                consulta = obtener_consulta_booleana()
                tokens = _tokenizar_booleana(consulta)
                rpn = _a_rpn(tokens)
                if not universo and "NOT" in tokens:
                    raise ValueError("NOT no disponible con este backend")
                resultado = evaluar_rpn(rpn, buscar_fn, universo)
                nombres = ids_a_nombres(resultado, doc_name_fn)
                print("Documentos encontrados:", nombres)
            except ValueError as e:
                print(f"Error en la consulta: {e}")
        elif opcion == "5":
            print("Saliendo...")
            break
        else:
            print("Opción inválida. Intente de nuevo.")


if __name__ == "__main__":
    main()
