from pathlib import Path
import importlib


def run():
    base_dir = Path(__file__).parent
    corpus = base_dir / "corpus"
    assert corpus.exists(), f"Falta corpus en {corpus}"

    # Construir índice con BSBI
    indexar = importlib.import_module("indexar")
    comprimir = importlib.import_module("comprimir")

    bsbi = indexar.BSBI(tamaño_bloque=50)
    indice = bsbi.construir_indice(corpus)

    # Comprimir
    comp = comprimir.comprimir_indice(indice, block_size=8)

    # Persistir temporalmente en memoria (sin escribir disco)
    # Crear un lector comprimido sin archivos no es trivial;
    # verificamos consistencia de postings desde offsets en memoria.

    # Selección de 3 términos si existen
    terms = list(comp.lexicon_terms_order)[:3]
    assert terms, "No hay términos en el índice"

    # Helper para decodificar VB
    def vb_decode_stream(data: bytes):
        nums = []
        n = 0
        for b in data:
            if b & 0x80:
                n = (n << 7) | (b & 0x7F)
                nums.append(n)
                n = 0
            else:
                n = (n << 7) | b
        return nums

    def from_dgaps(gaps):
        acc = 0
        out = []
        for g in gaps:
            acc += g
            out.append(acc)
        return out

    for t in terms:
        # BSBI postings
        bsbi_list = indice.get(t, [])

        # Comprimido -> decodificar desde blob por offset
        start, length = comp.postings_offsets[t]
        blob = comp.postings_bytes[start : start + length]
        gaps = vb_decode_stream(blob)
        decomp = from_dgaps(gaps)
        # Mapear a doc_ids originales si corresponde
        if comp.rev_doc_id_map:
            decomp_docs = [comp.rev_doc_id_map[i] for i in decomp]
        else:
            decomp_docs = decomp

        # Comparar con listas equivalentes (mapea comp a labels si aplica)
        if comp.rev_doc_id_map:
            comp_list = [comp.rev_doc_id_map[i] for i in decomp]
        else:
            comp_list = decomp
        assert (
            bsbi_list == comp_list
        ), f"Postings difieren para '{t}': {bsbi_list} vs {comp_list}"

    print("Smoke test OK: postings coinciden para 3 términos.")


if __name__ == "__main__":
    run()
