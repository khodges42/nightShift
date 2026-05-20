from datetime import datetime, timedelta, timezone

from pastebin_app import create_app


def client(tmp_path):
    app = create_app(tmp_path / "pastebin.sqlite3")
    app.config["TESTING"] = True
    return app.test_client()


def test_create_and_view_snippet(tmp_path):
    test_client = client(tmp_path)
    response = test_client.post(
        "/snippets",
        json={"title": "Hello", "body": "print('hi')", "language": "python", "tags": "demo,test"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 201
    snippet_id = response.get_json()["id"]
    view = test_client.get(f"/snippets/{snippet_id}", headers={"Accept": "application/json"})
    assert view.status_code == 200
    assert view.get_json()["language"] == "python"


def test_list_search_and_filters(tmp_path):
    test_client = client(tmp_path)
    test_client.post("/snippets", json={"title": "Python note", "body": "flask route", "language": "python", "tags": "web"})
    test_client.post("/snippets", json={"title": "SQL note", "body": "select", "language": "sql", "tags": "data"})

    search = test_client.get("/snippets?q=flask", headers={"Accept": "application/json"}).get_json()
    language = test_client.get("/snippets?language=sql", headers={"Accept": "application/json"}).get_json()
    tag = test_client.get("/snippets?tag=web", headers={"Accept": "application/json"}).get_json()

    assert [item["title"] for item in search] == ["Python note"]
    assert [item["title"] for item in language] == ["SQL note"]
    assert [item["title"] for item in tag] == ["Python note"]


def test_expired_snippet_hidden_and_direct_lookup_gone(tmp_path):
    test_client = client(tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = test_client.post("/snippets", json={"title": "Old", "body": "gone", "expires_at": expired}, headers={"Accept": "application/json"})
    snippet_id = response.get_json()["id"]

    listed = test_client.get("/snippets", headers={"Accept": "application/json"}).get_json()
    direct = test_client.get(f"/snippets/{snippet_id}", headers={"Accept": "application/json"})

    assert listed == []
    assert direct.status_code == 410
