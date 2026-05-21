from deaddrop_app.app import create_app


def _create(client, title, body, **metadata):
    response = client.post("/snippets", json={"title": title, "body": body, **metadata})
    assert response.status_code == 201
    return response.get_json()["id"]


def test_list_snippets_newest_first(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    first_id = _create(client, "First", "older")
    second_id = _create(client, "Second", "newer")

    response = client.get("/snippets")

    assert response.status_code == 200
    ids = [snippet["id"] for snippet in response.get_json()]
    assert ids[:2] == [second_id, first_id]


def test_search_filters_by_title_or_body(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    _create(client, "Python note", "ordinary body")
    _create(client, "Other", "contains needle")

    response = client.get("/snippets?q=python")
    assert [snippet["title"] for snippet in response.get_json()] == ["Python note"]

    response = client.get("/snippets?q=needle")
    assert [snippet["title"] for snippet in response.get_json()] == ["Other"]


def test_language_and_tag_filters(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    _create(client, "Python", "body", language="python", tags=["code", "demo"])
    _create(client, "Text", "body", language="text", tags=["notes"])

    response = client.get("/snippets?language=python")
    assert [snippet["title"] for snippet in response.get_json()] == ["Python"]

    response = client.get("/snippets?tag=notes")
    assert [snippet["title"] for snippet in response.get_json()] == ["Text"]
