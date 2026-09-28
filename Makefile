.PHONY: seed test serve docker-up health metrics

PYTHONPATH := ../stubs/python:.
export PYTHONPATH
export SAHIIXX_DB ?= /tmp/sahiixx_live.db

seed:
	cd service && python3 demo_seed.py

test:
	cd service && python3 test_revenue_path.py

serve:
	cd service && python3 -m uvicorn app:app --host 0.0.0.0 --port 8080

docker-up:
	docker compose -f service/docker-compose.yml up --build -d

health:
	curl -s http://127.0.0.1:8080/health | python3 -m json.tool

metrics:
	curl -s 'http://127.0.0.1:8080/v1/metrics?tenant_id=tenant-dubai-re' | python3 -m json.tool
