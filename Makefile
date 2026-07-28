PYTHON ?= python3
ENV = PYTHONPATH=src

.PHONY: test examples check install audit-demo clean

install:
	$(PYTHON) -m pip install -e .

test:
	$(ENV) $(PYTHON) -m unittest discover -s tests -v

examples:
	$(ENV) $(PYTHON) scripts/rebuild_examples.py

check:
	$(PYTHON) -m compileall -q src tests scripts
	$(ENV) $(PYTHON) -m unittest discover -s tests -v
	$(ENV) $(PYTHON) scripts/rebuild_examples.py --check
	$(PYTHON) scripts/security_scan.py
	$(PYTHON) scripts/check_docs.py

audit-demo:
	$(ENV) $(PYTHON) -m media_economics_audit audit examples/paired/baseline.jsonl --policy examples/paired/baseline-policy.json --out build/baseline --fail-on never
	$(ENV) $(PYTHON) -m media_economics_audit audit examples/paired/optimized.jsonl --policy examples/paired/optimized-policy.json --out build/optimized --fail-on never
	$(ENV) $(PYTHON) -m media_economics_audit compare build/baseline/audit.json build/optimized/audit.json --out build/comparison --name local-demo

clean:
	rm -rf build dist *.egg-info src/*.egg-info
