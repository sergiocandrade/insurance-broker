import unittest

from fastapi.testclient import TestClient

from src.presentation.apis.bff.main import app


class BffApiTests(unittest.TestCase):
    def test_health(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()