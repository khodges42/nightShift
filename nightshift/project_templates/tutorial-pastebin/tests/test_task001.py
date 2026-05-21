from pastebin_app.app import create_app


def test_create_snippet_returns_created_snippet_id(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    response = client.post(
        "/snippets",
        json={
            "title": "Example",
            "body": "hello",
        },
    )

    assert response.status_code == 201
    data = response.get_json()
    assert isinstance(data["id"], int)
    assert (tmp_path / "snippets.db").exists()


def test_view_snippet_returns_persisted_fields(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    created = client.post(
        "/snippets",
        json={
            "title": "View me",
            "body": "stored body",
        },
    ).get_json()

    response = client.get(f"/snippets/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": created["id"],
        "title": "View me",
        "body": "stored body",
    }
    assert (tmp_path / "snippets.db").exists()


def test_view_missing_snippet_returns_404(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    response = client.get("/snippets/999")

    assert response.status_code == 404
