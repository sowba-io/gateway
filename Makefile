POETRY ?= poetry

_default: test

install-dev:
	$(POETRY) install

install:
	$(POETRY) install  --no-dev

format:
	$(POETRY) run isort .
	$(POETRY) run black .

lint:
	$(POETRY) run isort --check-only .
	$(POETRY) run black --check .
	$(POETRY) run flake8 --config setup.cfg

mypy:
	$(POETRY) run mypy -p sowba_gateway

test:
	$(POETRY) run pytest tests

coverage:
	$(POETRY) run pytest -v tests -s --tb=native -v --cov=sowba_gateway --cov-report xml

run-http-dev:
	$(POETRY) run http --env-file=.env.local --reload

run-http:
	$(POETRY) run http

.PHONY: clean install install-dev test run-http run-http-dev
