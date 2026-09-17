
import httpx
from src.api.api_client import _validate_page
import unittest


class TestApiClient(unittest.TestCase):

    def test_rejects_limit_greater_than_expected(self, ):
        payload = {
            "carts": [
            {
            "id": 1,
            }
        ],
        "total": 1,
        "skip": 0,
        "limit": 20
        }
 
        response = httpx.Response(200, json=payload)

        with self.assertRaisesRegex(
            ValueError,
            r"^Unexpected limit: expected=1, returned=20$",
        ):
            _validate_page(response, "carts", limit=10, skip=0, expected_total=1)


    def test_response_limit_less_than_requested(self):
        payload = {
            "carts": [{"id": i} for i in range(8)],
        "total": 8,
        "skip": 0,
        "limit": 8
        }

        response = httpx.Response(200, json=payload)
        items, total = _validate_page(response, "carts", limit=10, skip=0, expected_total=8)
        self.assertEqual(len(items), 8)
        self.assertEqual(total, 8)

    def test_missing_total(self):
        payload = {
            "carts": [{"id": i} for i in range(8)],
            "skip": 0,
            "limit": 8
        }

        response = httpx.Response(200, json=payload)

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=8)
        self.assertEqual("Missing required fields in carts response: ['total']", str(context.exception))


    def test_send_html_response(self):
        response = httpx.Response(200, content="<html></html>", headers={"Content-Type": "text/html"})

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=8)
        self.assertEqual("Expected application/json, received text/html", str(context.exception))

    def test_invalid_json_response(self):
        response = httpx.Response(200, content="invalid json", headers={"Content-Type": "application/json"})

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=8)
        self.assertEqual("Response does not contain valid JSON", str(context.exception))

    def test_resource_not_a_list(self):
        payload = {
            "carts": {"id": 1},
            "total": 1,
            "skip": 0,
            "limit": 1
        }

        response = httpx.Response(200, json=payload)

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=1)
        self.assertEqual("Carts response 'carts' field is not a list", str(context.exception))


    def test_missing_resource(self):
        payload = {
            "limit": 1,
            "total": 1,
            "skip": 0,
        }

        response = httpx.Response(200, json=payload)

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=8)
        self.assertEqual(
            "Missing required fields in carts response: ['carts']",
            str(context.exception)
        )

    def test_incorrect_skip(self):
        payload = {
            "carts": [{"id": i} for i in range(8)],
            "total": 8,
            "skip": 5,
            "limit": 8
        }

        response = httpx.Response(200, json=payload)

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=8, skip=0, expected_total=8)
        self.assertEqual("Unexpected skip: requested=0, returned=5", str(context.exception))

    def test_item_without_id(self):
        payload = {
            "carts": [{"name": "item without id"}],
            "total": 1,
            "skip": 0,
            "limit": 1
        }

        response = httpx.Response(200, json=payload)

        with self.assertRaises(ValueError) as context:
            _validate_page(response, "carts", limit=10, skip=0, expected_total=1)
        self.assertEqual("Invalid item in 'carts'", str(context.exception))


    # fuente válida con total=0;
    # unión de dos páginas;
    # IDs repetidos entre páginas;
    # parámetros limit, skip y select;
    # reintentos de timeout, 429 y 503;
    # ausencia de reintentos para 400 y 404;
    # agotamiento del máximo de reintentos;
    # guardado raw, hash y protección contra sobrescritura;
    # estados finales del manifiesto.
    # total que cambia entre páginas;