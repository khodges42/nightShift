from pastebin_app.app import create_app


def test_create_snippet_accepts_optional_metadata(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    response = client.post(
        "/snippets",
        json={
            "title": "Tagged",
            "body": "metadata body",
            "language": "python",
            "tags": ["alpha", "beta"],
            "expires_at": "2030-01-01T00:00:00",
        },
    )

    assert response.status_code == 201
    assert isinstance(response.get_json()["id"], int)
    assert (tmp_path / "snippets.db").exists()


def test_view_snippet_returns_optional_metadata(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    created = client.post(
        "/snippets",
        json={
            "title": "Tagged",
            "body": "metadata body",
            "language": "python",
            "tags": ["alpha", "beta"],
            "expires_at": "2030-01-01T00:00:00",
        },
    ).get_json()

    response = client.get(f"/snippets/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == {
        "id": created["id"],
        "title": "Tagged",
        "body": "metadata body",
        "language": "python",
        "tags": ["alpha", "beta"],
        "expires_at": "2030-01-01T00:00:00",
    }
    assert (tmp_path / "snippets.db").exists()
