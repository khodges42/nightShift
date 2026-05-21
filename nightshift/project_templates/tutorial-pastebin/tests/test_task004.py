from pastebin_app.app import create_app


def test_expired_snippets_are_excluded_from_listing(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    client.post(
        "/snippets",
        json={"title": "Expired", "body": "old", "expires_at": "2000-01-01T00:00:00"},
    )
    active = client.post(
        "/snippets",
        json={"title": "Active", "body": "new", "expires_at": "2999-01-01T00:00:00"},
    ).get_json()

    response = client.get("/snippets")

    assert response.status_code == 200
    assert [snippet["id"] for snippet in response.get_json()] == [active["id"]]


def test_direct_lookup_of_expired_snippet_returns_410(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    expired = client.post(
        "/snippets",
        json={"title": "Expired", "body": "old", "expires_at": "2000-01-01T00:00:00"},
    ).get_json()

    response = client.get(f"/snippets/{expired['id']}")

    assert response.status_code == 410


def test_non_expiring_snippet_remains_visible(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    created = client.post("/snippets", json={"title": "Forever", "body": "body"}).get_json()

    response = client.get(f"/snippets/{created['id']}")

    assert response.status_code == 200
    assert response.get_json()["title"] == "Forever"
