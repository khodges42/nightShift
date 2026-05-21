from deaddrop_app.app import create_app


def test_root_shows_snippet_list_html(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()
    client.post("/snippets", json={"title": "Visible", "body": "body"})

    response = client.get("/")

    assert response.status_code == 200
    assert "Visible" in response.get_data(as_text=True)


def test_new_snippet_form_loads(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    response = client.get("/new")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="title"' in html
    assert 'name="body"' in html
    assert 'name="language"' in html
    assert 'name="tags"' in html
    assert 'name="expires_at"' in html


def test_form_post_redirects_to_snippet_view(tmp_path):
    app = create_app(database_path=str(tmp_path / "snippets.db"))
    client = app.test_client()

    response = client.post(
        "/new",
        data={
            "title": "Form title",
            "body": "Form body",
            "language": "text",
            "tags": "forms,html",
            "expires_at": "",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/snippets/1")
