from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_parent


def _create_student(client: TestClient, tokens: dict, name: str = "Alice", year: int = 5) -> dict:
    resp = client.post(
        "/api/v1/parents/students",
        json={"display_name": name, "year_level": year},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_parent_can_create_student(client: TestClient):
    tokens = register_parent(client)
    student = _create_student(client, tokens)
    assert student["display_name"] == "Alice"
    assert student["year_level"] == 5
    assert student["first_login_completed"] is False
    assert "login_email" in student
    assert "temp_password" in student


def test_student_credentials_returned_on_creation(client: TestClient):
    tokens = register_parent(client)
    student = _create_student(client, tokens)
    assert "@students.hscai.internal" in student["login_email"]
    assert len(student["temp_password"]) >= 8


def test_parent_can_list_students(client: TestClient):
    tokens = register_parent(client)
    _create_student(client, tokens, "Alice")
    _create_student(client, tokens, "Bob", year=6)
    resp = client.get("/api/v1/parents/students", headers=auth_headers(tokens))
    assert resp.status_code == 200
    names = {s["display_name"] for s in resp.json()}
    assert names == {"Alice", "Bob"}


def test_parent_cannot_create_more_than_3_students(client: TestClient):
    tokens = register_parent(client)
    for i in range(3):
        _create_student(client, tokens, f"Child{i}")
    resp = client.post(
        "/api/v1/parents/students",
        json={"display_name": "FourthChild", "year_level": 5},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 409


def test_parent_cannot_access_another_parents_students(client: TestClient):
    tokens_a = register_parent(client, email="a@test.com")
    tokens_b = register_parent(client, email="b@test.com")

    student = _create_student(client, tokens_a, "AliceA")

    # Parent B tries to patch Parent A's student — must get 404 (not found for this parent)
    resp = client.patch(
        f"/api/v1/parents/students/{student['id']}",
        json={"display_name": "Hacked"},
        headers=auth_headers(tokens_b),
    )
    assert resp.status_code == 404


def test_parent_can_update_student(client: TestClient):
    tokens = register_parent(client)
    student = _create_student(client, tokens, "Alice", year=5)
    resp = client.patch(
        f"/api/v1/parents/students/{student['id']}",
        json={"display_name": "Alicia", "year_level": 6},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Alicia"
    assert resp.json()["year_level"] == 6


def test_parent_can_deactivate_student(client: TestClient):
    tokens = register_parent(client)
    student = _create_student(client, tokens, "Alice")
    resp = client.delete(
        f"/api/v1/parents/students/{student['id']}",
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 204
    # Student no longer appears in list
    students = client.get("/api/v1/parents/students", headers=auth_headers(tokens)).json()
    assert not any(s["id"] == student["id"] for s in students)


def test_student_count_resets_after_deactivation(client: TestClient):
    tokens = register_parent(client)
    for i in range(3):
        s = _create_student(client, tokens, f"C{i}")
    # Deactivate one
    client.delete(f"/api/v1/parents/students/{s['id']}", headers=auth_headers(tokens))
    # Now we should be able to create again
    resp = client.post(
        "/api/v1/parents/students",
        json={"display_name": "NewChild", "year_level": 4},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 201


def test_invalid_year_level_rejected(client: TestClient):
    tokens = register_parent(client)
    resp = client.post(
        "/api/v1/parents/students",
        json={"display_name": "Kid", "year_level": 10},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


def test_unauthenticated_student_list_returns_401(client: TestClient):
    resp = client.get("/api/v1/parents/students")
    assert resp.status_code == 401
