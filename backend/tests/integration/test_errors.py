"""Safe error response and log-redaction integration tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


def test_database_errors_are_generic_and_do_not_log_query_details(
    test_app: FastAPI, caplog
) -> None:
    secret_detail = "private-database-connection-detail"

    def fail_database_operation() -> None:
        raise SQLAlchemyError(secret_detail)

    test_app.add_api_route("/_test/database-error", fail_database_operation, methods=["GET"])
    with TestClient(test_app) as client:
        response = client.get("/_test/database-error")

    assert response.status_code == 503
    assert secret_detail not in response.text
    assert secret_detail not in caplog.text
    assert response.json()["detail"]["request_id"]
