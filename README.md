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

## Cognito Sign-In

Enable `ALLOW_USER_PASSWORD_AUTH` on your Cognito user pool app client.
Enable the app client's `PreventUserExistenceErrors` option to avoid revealing
whether a username exists. Use HTTPS when deploying this password-based endpoint.

Configure the application environment before starting the server:

Configuration is centralized in `src/infrastructure/config/settings.py` using
Pydantic Settings and injected into the sign-in endpoint. It reads `AWS_REGION`
(falling back to `AWS_DEFAULT_REGION`), `COGNITO_CLIENT_ID`, and
`COGNITO_CLIENT_SECRET` from the environment. Empty values are treated as unset,
and the client secret is masked in the settings object's representation. All
three fields are uppercase, required, and nonempty. Environment variable names
are case-sensitive.

```sh
export AWS_REGION=us-east-1
export COGNITO_CLIENT_ID=your-app-client-id
export COGNITO_CLIENT_SECRET=your-app-client-secret
```

Use a Cognito app client with a secret and provide `COGNITO_CLIENT_SECRET` through
your environment or secret manager. The server computes Cognito's `SECRET_HASH`;
the client secret must never be sent by the frontend. A user pool ID is not
required for this authentication flow.

For Compose, these variables can also be configured in `docker/.env`, which
the Makefile loads. Rebuild the image to install the Cognito SDK:

```sh
make build-bff
make run-bff
```

Compose exposes the API at http://localhost:5002. Local Uvicorn and the direct
Docker command above use port `8510` instead.

```sh
curl -X POST http://localhost:5002/auth/sign-in \
	-H 'Content-Type: application/json' \
	-d '{"username":"user@example.com","password":"example-password"}'
```

Successful authentication returns `access_token`, `id_token`, `refresh_token`,
`token_type`, and `expires_in`. If Cognito requires MFA or a new password,
the response instead contains `challenge_name`, `challenge_parameters`, and
`session`. This endpoint does not complete challenges; the caller must not
treat a challenge response as completed authentication.

Errors return `401` for invalid credentials, `403` for required account
verification or password reset, `429` for throttling, `502` for other Cognito
errors, or `503` for missing configuration or an unavailable service.

## Dependency Injection

`src/containers.py` defines the `dependency-injector` container for the API:
settings are a lazy singleton, while the authentication engine and sign-in use
case use factory providers. The FastAPI entry point wires the route module and
stores the container at `app.state.container`. Restart the application after
changing environment settings that have already been loaded.

Tests can replace dependencies using provider overrides, for example
`with app.state.container.authentication_engine.override(fake_engine):`.
Domain interfaces and use cases do not depend on the container or FastAPI.

## Tests

```sh
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m unittest discover -s tests/presentation -p 'test_*.py' -v
```