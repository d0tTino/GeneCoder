.PHONY: openai-testing lint

# Launch the CUA server demo and GeneCoder Flet GUI
openai-testing:
	./scripts/start_flet_and_cua.sh

lint:
	.venv/bin/pre-commit run --files $(shell git ls-files '*.py')
