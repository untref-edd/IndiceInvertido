from pathlib import Path
import json


def sizeof_uncompressed(index: dict[str, list]) -> tuple[int, int, int]:
    # Estimación aproximada:
    # - bytes de términos (UTF-8)
    # - 4 bytes por docID (asumiendo enteros sin compresión)
    vocab_bytes = sum(len(t.encode("utf-8")) for t in index.keys())
    postings_count = sum(len(pl) for pl in index.values())
    postings_bytes_est = postings_count * 4
    return vocab_bytes + postings_bytes_est, vocab_bytes, postings_count


def human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def contar_tokens(corpus_path: Path, bsbi) -> int:
    total = 0
    for p in corpus_path.glob("*.txt"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        total += len(bsbi.tokenizar(txt))
    return total


def guardar_comprimido(base_dir: Path, comp) -> None:
    idx_dir = base_dir / "index"
    idx_dir.mkdir(exist_ok=True)

    # Guardar blobs binarios
    (idx_dir / "postings.bin").write_bytes(comp.postings_bytes)
    (idx_dir / "lexicon.bin").write_bytes(comp.lexicon_bytes)

    # Guardar metadatos JSON
    with open(idx_dir / "postings_offsets.json", "w", encoding="utf-8") as f:
        json.dump(comp.postings_offsets, f, ensure_ascii=False)

    with open(idx_dir / "doc_maps.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "doc_id_map": comp.doc_id_map,
                "rev_doc_id_map": comp.rev_doc_id_map,
                "terms_order": comp.lexicon_terms_order,
                "block_size": comp.lexicon_block_size,
            },
            f,
            ensure_ascii=False,
        )


def main() -> None:
    base_dir = Path(__file__).parent
    corpus_path = base_dir / "corpus"
    if not corpus_path.exists():
        raise SystemExit(f"No se encontró el corpus en {corpus_path}")

    # 1) Construir índice con BSBI
    # Importaciones locales para evitar problemas de rutas con linters
    import importlib
    import sys

    sys.path.insert(0, str(base_dir))
    ii = importlib.import_module("indexar")
    comprimir = importlib.import_module("comprimir")

    bsbi = ii.BSBI(tamaño_bloque=50)
    print(f"Construyendo índice desde: {corpus_path}\n")
    index = bsbi.construir_indice(corpus_path)

    # Estadísticas
    num_docs = len(list(corpus_path.glob("*.txt")))
    num_terms = len(index)
    tokens = contar_tokens(corpus_path, bsbi)
    total_bytes_est, _vocab_bytes, postings_count = sizeof_uncompressed(index)
    print("=== Estadísticas índice (sin compresión) ===")
    print(f"Documentos: {num_docs}")
    print(f"Palabras (tokens) procesadas: {tokens}")
    print(f"Términos únicos: {num_terms}")
    print(f"Postings totales: {postings_count}")
    print(f"Tamaño estimado: {human(total_bytes_est)}")

    # 2) Comprimir
    comp = comprimir.comprimir_indice(index, block_size=8)
    print("\n=== Estadísticas índice comprimido ===")
    lex_bytes = len(comp.lexicon_bytes)
    post_bytes = len(comp.postings_bytes)
    print(f"Lexicon bytes (mem): {human(lex_bytes)}")
    print(f"Postings bytes (mem): {human(post_bytes)}")
    print(f"Tamaño total (mem): {human(lex_bytes + post_bytes)}")

    # 3) Guardar a disco en carpeta index/
    guardar_comprimido(base_dir, comp)
    print(f"\nÍndice comprimido guardado en: {base_dir / 'index'}")
    # Métricas reales en disco
    idx_dir = base_dir / "index"
    on_disk_lex = (idx_dir / "lexicon.bin").stat().st_size
    on_disk_post = (idx_dir / "postings.bin").stat().st_size
    print(f"Tamaño en disco - lexicon.bin: {human(on_disk_lex)}")
    print(f"Tamaño en disco - postings.bin: {human(on_disk_post)}")
    print(f"Total en disco: {human(on_disk_lex + on_disk_post)}")

    # 4) Ejecutar el buscador interactivo (usará índice comprimido)
    # Aseguramos importación desde este mismo directorio
    buscar = importlib.import_module("buscar")
    buscar.main()


if __name__ == "__main__":
    main()
