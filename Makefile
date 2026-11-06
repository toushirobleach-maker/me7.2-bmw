PYTHON ?= python3

.PHONY: help test verify audit public-check
help:
	@echo "make test | make audit | make public-check | make verify (offline only)"
test:
	$(PYTHON) -m unittest discover -s 08_tests -v
audit:
	$(PYTHON) 09_re_tools/audit_repo.py
public-check:
	$(PYTHON) 09_re_tools/check_public_tree.py
verify:
	$(PYTHON) 09_re_tools/manifest.py verify
