from ii import BSBI  # Usamos la clase BSBI definida en ii.py
from pathlib import Path

def mostrar_menu():
    print("\n=== Búsqueda en Índice Invertido ===")
    print("Algunas palabras para probar: hobbit, anillo, elfo, mago, gato, perro, ratón")
    print("1. Buscar con AND")
    print("2. Buscar con OR")
    print("3. Buscar con NOT")
    print("4. Consulta booleana ((), AND, OR, NOT)")
    print("5. Salir")

def obtener_consulta():
    consulta = input("Ingrese términos de búsqueda separados por espacios: ")
    return consulta.strip().split()


def obtener_consulta_booleana():
    return input(
        "Ingrese una consulta booleana (use AND, OR, NOT y paréntesis): "
    ).strip()


def _tokenizar_booleana(consulta: str):
    """Tokeniza una consulta booleana preservando paréntesis y operadores.

    Retorna una lista de tokens donde los operadores están en mayúsculas
    (AND, OR, NOT) y los términos tal cual fueron escritos.
    """
    import re
    # Paréntesis, operadores completos, o palabras (unicode)
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
    """Convierte la lista de tokens a RPN con Shunting Yard.

    Precedencias: NOT > AND > OR. NOT es unario y asociativo a la derecha.
    Devuelve una lista de tokens en RPN.
    """
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
            ops.pop()  # quitar '('
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
            # término
            salida.append(("TERM", t))

    while ops:
        top = ops.pop()
        if top in ("(", ")"):
            raise ValueError("Paréntesis desbalanceados")
        salida.append(top)

    return salida


def _universo_docs(bsbi: BSBI):
    u = set()
    for docs in bsbi.indice_final.values():
        u.update(docs)
    return u


def evaluar_rpn(rpn, bsbi: BSBI, universo: set):
    """Evalúa la RPN devolviendo un set de doc_ids."""
    pila = []
    for t in rpn:
        if isinstance(t, tuple) and t and t[0] == "TERM":
            term = t[1]
            pila.append(set(bsbi.buscar(term)))
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


def busqueda_and(bsbi: BSBI, terminos):
    """Intersección de documentos que contienen todos los términos."""
    sets = [set(bsbi.buscar(term)) for term in terminos if term]
    return set.intersection(*sets) if sets else set()


def busqueda_or(bsbi: BSBI, terminos):
    """Unión de documentos que contienen al menos uno de los términos."""
    sets = [set(bsbi.buscar(term)) for term in terminos if term]
    return set.union(*sets) if sets else set()


def busqueda_not(bsbi: BSBI, terminos):
    """Documentos que NO contienen ninguno de los términos dados."""
    # Universo de documentos presentes en el índice
    todos_docs = set()
    for docs in bsbi.indice_final.values():
        todos_docs.update(docs)
    # Docs a excluir (contienen cualquiera de los términos)
    sets = [set(bsbi.buscar(term)) for term in terminos if term]
    excluidos = set.union(*sets) if sets else set()
    return todos_docs - excluidos


def main():
    # Construir el índice con BSBI a partir del corpus incluido
    corpus_path = Path(__file__).parent / "corpus"
    bsbi = BSBI(tamaño_bloque=50)
    print(f"Construyendo índice desde: {corpus_path}\n")
    bsbi.construir_indice(corpus_path)

    universo = _universo_docs(bsbi)

    while True:
        mostrar_menu()
        opcion = input("Seleccione una opción: ").strip()
        if opcion == "1":
            terminos = obtener_consulta()
            resultado = busqueda_and(bsbi, terminos)
            print("\nDocumentos encontrados:", sorted(resultado))
        elif opcion == "2":
            terminos = obtener_consulta()
            resultado = busqueda_or(bsbi, terminos)
            print("\nDocumentos encontrados:", sorted(resultado))
        elif opcion == "3":
            terminos = obtener_consulta()
            resultado = busqueda_not(bsbi, terminos)
            print("\nDocumentos encontrados:", sorted(resultado))
        elif opcion == "4":
            print("\nEjemplo de consulta booleana: (gato OR perro) AND NOT ratón")
            try:
                consulta = obtener_consulta_booleana()
                tokens = _tokenizar_booleana(consulta)
                rpn = _a_rpn(tokens)
                resultado = evaluar_rpn(rpn, bsbi, universo)
                print("Documentos encontrados:", sorted(resultado))
            except ValueError as e:
                print(f"Error en la consulta: {e}")
        elif opcion == "5":
            print("Saliendo...")
            break
        else:
            print("Opción inválida. Intente de nuevo.")


if __name__ == "__main__":
    main()
