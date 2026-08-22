.PHONY: check test

check:
	python -m ruff format --check .
	python -m ruff check .
	pyright
	PYTHONPATH=src lint-imports
	uvx --from semgrep==1.174.0 semgrep --config semgrep.yml src tests
	uvx --from vulture==2.16 vulture src/trajcert --min-confidence 100 --ignore-names table,where,compression,use_dictionary,write_statistics,field_type,nullable,value_type,fields,tz,unit
	uvx --from deptry==0.25.1 deptry .

test:
	coverage run -m pytest -q
	coverage report
