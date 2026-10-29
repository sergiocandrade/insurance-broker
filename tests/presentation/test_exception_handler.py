import unittest
from unittest.mock import Mock

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from application.usecase_exception import UseCaseException
from domain.exceptions.authentication import AuthenticationError
from domain.exceptions.broker import BrokerNotFoundException
from domain.exceptions.customer import CustomerNotFoundException
from domain.exceptions.domain import DomainException, ForbiddenException, NotFoundException
from infrastructure.persistence.exceptions import PersistenceError
from domain.exceptions.user import UserNotFoundException
from presentation.apis.bff.exception_handler import AUTHENTICATION_STATUS_CODES, handle_exceptions, register_exception_handlers
from presentation.apis.bff.main import app


class ExceptionHandlerTests(unittest.TestCase):
    def test_domain_and_application_errors_are_translated(self) -> None:
        for error, expected_status in (
            (DomainException("Invalid operation"), 400),
            (UseCaseException("Signup is not allowed"), 400),
            (NotFoundException("Broker"), 404),
            (CustomerNotFoundException(), 404),
            (UserNotFoundException(), 404),
            (BrokerNotFoundException(), 403),
            (ForbiddenException("Access denied"), 403),
        ):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(HTTPException) as translated:
                    with handle_exceptions():
                        raise error
                self.assertEqual(translated.exception.status_code, expected_status)
                self.assertEqual(translated.exception.detail, str(error))

    def test_authentication_status_codes_and_headers_are_preserved(self) -> None:
        for reason, expected_status in AUTHENTICATION_STATUS_CODES.items():
            with self.subTest(reason=reason):
                with self.assertRaises(HTTPException) as translated:
                    with handle_exceptions():
                        raise AuthenticationError(reason, "Authentication detail")
                self.assertEqual(translated.exception.status_code, expected_status)
                if expected_status == 401:
                    self.assertEqual(translated.exception.headers, {"WWW-Authenticate": "Bearer"})

    def test_infrastructure_details_are_not_exposed(self) -> None:
        for error in (
            PersistenceError("private database details"),
            AuthenticationError("service_error", "private AWS details"),
            AuthenticationError("service_unavailable", "private connection details"),
        ):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(HTTPException) as translated:
                    with handle_exceptions():
                        raise error
                self.assertNotIn("private", str(translated.exception.detail))

    def test_persistence_errors_use_generic_safe_detail(self) -> None:
        with self.assertRaises(HTTPException) as translated:
            with handle_exceptions():
                raise PersistenceError("private database details")
        self.assertEqual(translated.exception.status_code, 503)
        self.assertEqual(translated.exception.detail, "Persistence service unavailable")

    def test_unknown_authentication_reason_is_safe(self) -> None:
        with self.assertRaises(HTTPException) as translated:
            with handle_exceptions():
                raise AuthenticationError("unknown_reason", "private details")
        self.assertEqual(translated.exception.status_code, 500)
        self.assertEqual(translated.exception.detail, "Authentication failed")

    def test_existing_http_exceptions_and_programming_errors_are_not_replaced(self) -> None:
        for error in (HTTPException(status_code=418, detail="Existing HTTP error"), RuntimeError("Unexpected bug")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)) as raised:
                    with handle_exceptions():
                        raise error
                self.assertIs(raised.exception, error)

class EndpointExceptionHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.credentials = {"username": "test-user", "password": "test-password"}

    def test_domain_and_use_case_errors_reach_http_responses(self) -> None:
        for error, expected_status in (
            (UserNotFoundException(), 404),
            (DomainException("Invalid operation"), 400),
            (UseCaseException("Signup is not allowed"), 400),
            (AuthenticationError("invalid_credentials", "Invalid credentials"), 401),
            (AuthenticationError("user_exists", "Already registered"), 409),
            (PersistenceError("private database details"), 503),
        ):
            with self.subTest(error=type(error).__name__):
                use_case = Mock()
                use_case.execute.side_effect = error
                with app.state.container.sign_in_use_case.override(use_case):
                    response = self.client.post("/auth/sign-in", json=self.credentials)
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private", response.text)
                if expected_status == 401:
                    self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_every_auth_endpoint_intercepts_use_case_errors(self) -> None:
        for method, path, provider_name, body in (
            ("POST", "/auth/sign-in", "sign_in_use_case", self.credentials),
            ("POST", "/auth/sign-up", "sign_up_use_case", {
                "email": "user@example.com", "phone": "+5511999999999", "region": "SP",
                "insurance_categories": ["Pessoas"],
            }),
            ("POST", "/auth/new-password", "complete_new_password_use_case", {
                "username": "test-user", "new_password": "new-password", "session": "test-session",
            }),
            ("POST", "/auth/reset-password", "request_password_reset_use_case", {"username": "test-user"}),
            ("POST", "/auth/reset-password/confirm", "confirm_password_reset_use_case", {
                "username": "test-user", "code": "123456", "new_password": "new-password",
            }),
            ("GET", "/auth/me", "get_current_user_use_case", None),
        ):
            with self.subTest(path=path):
                use_case = Mock()
                use_case.execute.side_effect = UseCaseException("Operation is not allowed")
                with getattr(app.state.container, provider_name).override(use_case):
                    response = self.client.request(
                        method, path, json=body, headers={"Authorization": "Bearer test-access-token"},
                    )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"detail": "Operation is not allowed"})

    def test_persistence_errors_use_generic_safe_detail(self) -> None:
        for path, provider_name, body in (
            ("/auth/sign-up", "sign_up_use_case", {
                "email": "user@example.com", "phone": "+5511999999999", "region": "SP",
                "insurance_categories": ["Pessoas"],
            }),
        ):
            with self.subTest(path=path):
                use_case = Mock()
                use_case.execute.side_effect = PersistenceError("private database details")
                with getattr(app.state.container, provider_name).override(use_case):
                    response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["detail"], "Persistence service unavailable")
                self.assertNotIn("private", response.text)

    def test_request_validation_still_returns_422(self) -> None:
        use_case = Mock()
        with app.state.container.sign_in_use_case.override(use_case):
            response = self.client.post("/auth/sign-in", json={"username": "test-user"})

        self.assertEqual(response.status_code, 422)
        use_case.execute.assert_not_called()


class GlobalExceptionHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        register_exception_handlers(self.app)

    def test_new_router_is_intercepted_without_endpoint_wrapper(self) -> None:
        router = APIRouter(prefix="/new-router")

        @router.get("/failure")
        def failure():
            raise UseCaseException("Operation is not allowed")

        self.app.include_router(router)
        with TestClient(self.app) as client:
            response = client.get("/new-router/failure")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Operation is not allowed"})

    def test_async_endpoint_is_intercepted(self) -> None:
        @self.app.get("/async-failure")
        async def failure():
            raise UserNotFoundException()

        with TestClient(self.app) as client:
            response = client.get("/async-failure")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "User not found"})

    def test_domain_errors_from_dependencies_are_intercepted(self) -> None:
        def failing_dependency():
            raise ForbiddenException("Access denied")

        @self.app.get("/dependency-failure")
        def failure(dependency=Depends(failing_dependency)):
            return {"status": "unreachable"}

        with TestClient(self.app) as client:
            response = client.get("/dependency-failure")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Access denied"})

    def test_existing_http_exceptions_are_preserved(self) -> None:
        @self.app.get("/http-error")
        def failure():
            raise HTTPException(status_code=418, detail="Existing HTTP error", headers={"X-Custom": "kept"})

        with TestClient(self.app) as client:
            response = client.get("/http-error")

        self.assertEqual(response.status_code, 418)
        self.assertEqual(response.json(), {"detail": "Existing HTTP error"})
        self.assertEqual(response.headers["X-Custom"], "kept")

    def test_programming_and_response_validation_errors_still_return_500(self) -> None:
        @self.app.get("/unexpected-error")
        def unexpected_error():
            raise RuntimeError("private programming details")

        @self.app.get("/invalid-response", response_model=dict[str, int])
        def invalid_response():
            return {"value": "not-an-integer"}

        with TestClient(self.app, raise_server_exceptions=False) as client:
            for path in ("/unexpected-error", "/invalid-response"):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 500)
                    self.assertNotIn("private", response.text)
