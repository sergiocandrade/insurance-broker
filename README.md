# sergiocandrade-insurance-broker-bff

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn presentation.apis.bff.main:app --app-dir src --host 127.0.0.1 --port 8510 --reload
```

- Health: http://localhost:8510/health
- Swagger UI: http://localhost:8510/docs
- OpenAPI schema: http://localhost:8510/openapi.json

## Run with Docker

```sh
docker build -f docker/Dockerfile_BFF -t insurance-broker-bff .
docker run --rm -p 8510:8510 insurance-broker-bff
```

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/presentation -p 'test_*.py' -v
```