.PHONY: help clean run test all

# Configuración
PYTHON := python3
INDEX_DIR := index
MAIN_SCRIPT := main.py
SEARCH_SCRIPT := buscar.py
TEST_SCRIPT := smoke_test_comprimido.py

help: ## Mostrar esta ayuda
	@echo "Makefile para Índice Invertido con Compresión"
	@echo ""
	@echo "Uso: make [target]"
	@echo ""
	@echo "Targets disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

run: ## Ejecutar demo completa (construir índice, comprimir y buscar)
	@echo "Ejecutando demo completa..."
	$(PYTHON) $(MAIN_SCRIPT)

search: ## Ejecutar el buscador interactivo
	@echo "Iniciando buscador interactivo..."
	$(PYTHON) $(SEARCH_SCRIPT)

test: ## Ejecutar test de validación de compresión
	@echo "Ejecutando smoke test..."
	$(PYTHON) $(TEST_SCRIPT)

clean: ## Limpiar índice construido y archivos temporales
	@echo "Limpiando índice y archivos temporales..."
	@rm -rf $(INDEX_DIR)
	@rm -rf __pycache__
	@rm -rf temp_blocks
	@rm -f *.pyc
	@echo "Limpieza completada."

clean-all: clean ## Limpiar todo incluyendo cache de Python
	@echo "Limpiando cache adicional..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Limpieza completa finalizada."

rebuild: clean run ## Limpiar y reconstruir índice desde cero

stats: ## Mostrar estadísticas del índice construido
	@if [ -d "$(INDEX_DIR)" ]; then \
		echo "Estadísticas del índice:"; \
		echo "  Archivos en index/:"; \
		ls -lh $(INDEX_DIR); \
		echo ""; \
		echo "  Tamaño total:"; \
		du -sh $(INDEX_DIR); \
	else \
		echo "No hay índice construido. Ejecutar 'make run' primero."; \
	fi

all: clean run test ## Limpiar, construir índice y ejecutar tests
	@echo "Proceso completo finalizado."
