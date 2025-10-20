"""
Implementación de algoritmos de construcción de índices invertidos.

Este módulo implementa el algoritmo BSBI (Blocked Sort-Based Indexing)
para la construcción eficiente de índices invertidos sobre grandes colecciones
de documentos.
"""

import re
import heapq
from collections import defaultdict
from pathlib import Path


class BSBI:
    """
    Blocked Sort-Based Indexing (BSBI)

    Algoritmo para construir índices invertidos que maneja colecciones
    de documentos que no caben en memoria RAM. Procesa los documentos en
    bloques, crea índices parciales ordenados, y luego los fusiona.
    """

    def __init__(self, tamaño_bloque=1000):
        """
        Inicializa el constructor de índices BSBI.

        Args:
            tamaño_bloque: Número de términos por bloque antes de
                escribir a disco
        """
        self.tamaño_bloque = tamaño_bloque
        self.indice_final = defaultdict(list)
        self.directorio_bloques = None

    def normalizar(self, texto):
        """Normaliza el texto a minúsculas y remueve puntuación."""
        texto = texto.lower()
        texto = re.sub(r"[^\w\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()

    def tokenizar(self, texto):
        """Divide el texto en tokens individuales."""
        return self.normalizar(texto).split()

    def parse_documento(self, doc_id, contenido):
        """
        Parsea un documento y retorna una lista de tuplas (término, doc_id).

        Args:
            doc_id: Identificador único del documento
            contenido: Texto del documento

        Returns:
            Lista de tuplas (término, doc_id)
        """
        tokens = self.tokenizar(contenido)
        # Retornar tuplas (término, doc_id) para cada token único
        terminos_unicos = set(tokens)
        return [(termino, doc_id) for termino in terminos_unicos]

    def invertir_bloque(self, pares_termino_docid):
        """
        Invierte un bloque de pares (término, doc_id) en un diccionario.

        Args:
            pares_termino_docid: Lista de tuplas (término, doc_id)

        Returns:
            Diccionario {término: [lista de doc_ids]}
        """
        indice_bloque = defaultdict(list)

        # Ordenar por término primero, luego por doc_id
        pares_ordenados = sorted(pares_termino_docid)

        # Agrupar doc_ids por término
        for termino, doc_id in pares_ordenados:
            if not indice_bloque[termino] or indice_bloque[termino][-1] != doc_id:
                indice_bloque[termino].append(doc_id)

        return dict(indice_bloque)

    def escribir_bloque_a_disco(self, indice_bloque, numero_bloque):
        """
        Escribe un índice de bloque a disco.

        Args:
            indice_bloque: Diccionario {término: [doc_ids]}
            numero_bloque: Número identificador del bloque
        """
        archivo_bloque = self.directorio_bloques / f"bloque_{numero_bloque}.txt"

        with open(archivo_bloque, "w", encoding="utf-8") as f:
            for termino in sorted(indice_bloque.keys()):
                doc_ids = ",".join(map(str, indice_bloque[termino]))
                f.write(f"{termino}\t{doc_ids}\n")

    def fusionar_bloques(self, num_bloques):
        """
        Fusiona todos los bloques en un índice final usando merge de k-vías.

        Args:
            num_bloques: Número total de bloques a fusionar
        """
        # Abrir todos los archivos de bloques
        archivos_bloques = []
        heap = []

        for i in range(num_bloques):
            archivo = open(
                self.directorio_bloques / f"bloque_{i}.txt",
                "r",
                encoding="utf-8",
            )
            archivos_bloques.append(archivo)

            # Leer primera línea de cada archivo
            linea = archivo.readline().strip()
            if linea:
                termino, doc_ids = linea.split("\t")
                doc_ids_list = doc_ids.split(",")
                # Heap: (término, doc_ids, índice_archivo)
                heapq.heappush(heap, (termino, doc_ids_list, i))

        # Merge de k-vías
        termino_actual = None
        doc_ids_acumulados = []

        while heap:
            termino, doc_ids, idx_archivo = heapq.heappop(heap)

            # Si es un nuevo término, guardar el anterior
            if termino_actual is not None and termino != termino_actual:
                self.indice_final[termino_actual] = sorted(set(doc_ids_acumulados))
                doc_ids_acumulados = []

            termino_actual = termino
            doc_ids_acumulados.extend(doc_ids)

            # Leer siguiente línea del mismo archivo
            linea = archivos_bloques[idx_archivo].readline().strip()
            if linea:
                termino, doc_ids = linea.split("\t")
                doc_ids_list = doc_ids.split(",")
                heapq.heappush(heap, (termino, doc_ids_list, idx_archivo))

        # Guardar el último término
        if termino_actual is not None:
            self.indice_final[termino_actual] = sorted(set(doc_ids_acumulados))

        # Cerrar archivos
        for archivo in archivos_bloques:
            archivo.close()

    def construir_indice(self, directorio_documentos, directorio_temp="./temp_blocks"):
        """
        Construye un índice invertido usando BSBI.

        Args:
            directorio_documentos: Ruta al directorio con documentos
            directorio_temp: Ruta al directorio temporal para bloques

        Returns:
            Diccionario {término: [lista de doc_ids ordenados]}
        """
        self.directorio_bloques = Path(directorio_temp)
        self.directorio_bloques.mkdir(exist_ok=True)

        directorio_docs = Path(directorio_documentos)

        # Fase 1: Procesar documentos en bloques
        pares_termino_docid = []
        numero_bloque = 0

        # Obtener lista de archivos ordenada
        archivos_docs = sorted(directorio_docs.glob("*.txt"))

        for doc_path in archivos_docs:
            doc_id = doc_path.stem  # Usar nombre de archivo como ID

            with open(doc_path, "r", encoding="utf-8") as f:
                contenido = f.read()

            # Parsear documento
            pares_doc = self.parse_documento(doc_id, contenido)
            pares_termino_docid.extend(pares_doc)

            # Si el bloque está lleno, procesarlo
            if len(pares_termino_docid) >= self.tamaño_bloque:
                indice_bloque = self.invertir_bloque(pares_termino_docid)
                self.escribir_bloque_a_disco(indice_bloque, numero_bloque)
                numero_bloque += 1
                pares_termino_docid = []

        # Procesar último bloque si tiene datos
        if pares_termino_docid:
            indice_bloque = self.invertir_bloque(pares_termino_docid)
            self.escribir_bloque_a_disco(indice_bloque, numero_bloque)
            numero_bloque += 1

        # Fase 2: Fusionar todos los bloques
        if numero_bloque > 0:
            self.fusionar_bloques(numero_bloque)

        return dict(self.indice_final)

    def buscar(self, termino):
        """
        Busca un término en el índice.

        Args:
            termino: Término a buscar

        Returns:
            Lista de doc_ids que contienen el término
        """
        termino_normalizado = self.normalizar(termino)
        return self.indice_final.get(termino_normalizado, [])


def ejemplo_bsbi():
    """Ejemplo de uso del algoritmo BSBI."""

    # Ruta al corpus de documentos
    directorio_corpus = Path(__file__).parent / "corpus"

    if not directorio_corpus.exists():
        print(f"Error: No se encuentra el directorio {directorio_corpus}")
        return

    print("=== Construcción de Índice Invertido con BSBI ===\n")

    # Crear constructor BSBI
    bsbi = BSBI(tamaño_bloque=50)

    # Construir índice
    print(f"Procesando documentos en {directorio_corpus}...")
    indice = bsbi.construir_indice(directorio_corpus)

    print(f"\nÍndice construido con {len(indice)} términos únicos")

    # Mostrar algunos términos de ejemplo
    print("\nMuestra de términos en el índice:")
    terminos_muestra = sorted(indice.keys())[:10]
    for termino in terminos_muestra:
        print(f"  {termino}: {indice[termino]}")

    print("\n=== Estadísticas del Índice ===")
    total_postings = sum(len(docs) for docs in indice.values())
    print(f"Total de términos: {len(indice)}")
    print(f"Total de postings: {total_postings}")
    print(f"Promedio de docs por término: {total_postings / len(indice):.2f}")


if __name__ == "__main__":
    ejemplo_bsbi()
