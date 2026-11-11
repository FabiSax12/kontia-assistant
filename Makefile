PY=./venv/bin/python

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

indexar:
	$(PY) -m app.rag.indexar

dev:
	$(PY) -m uvicorn app.main:app --reload --port 8000

eval:
	$(PY) tests/eval.py

.PHONY: install indexar dev eval
