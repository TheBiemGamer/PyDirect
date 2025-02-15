import pytest
from werkzeug.security import generate_password_hash
from pydirect.app import create_app, db


@pytest.fixture
def client():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    }
    app = create_app(test_config)
    with app.test_client() as client:
        with app.app_context():
            db.drop_all()
            db.create_all()
            User = app.User
            if not User.query.filter_by(username="admin").first():
                admin_user = User(
                    username="admin",
                    password=generate_password_hash("admin", method="pbkdf2:sha256"),
                )
                db.session.add(admin_user)
                db.session.commit()
        yield client


def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.get("/logout", follow_redirects=True)


def test_home_redirect(client):
    response = client.get("/", follow_redirects=True)
    assert b"login" in response.data.lower() or b"admin" in response.data.lower()


def test_login_valid(client):
    response = login(client, "admin", "admin")
    assert b"redirect" in response.data.lower() or b"admin" in response.data.lower()


def test_login_invalid(client):
    response = login(client, "admin", "wrongpassword")
    assert b"invalid credentials" in response.data.lower()


def test_logout(client):
    login(client, "admin", "admin")
    response = logout(client)
    assert b"login" in response.data.lower()


def test_add_redirect(client):
    login(client, "admin", "admin")
    response = client.post(
        "/admin",
        data={"source": "test", "destination": "http://example.com"},
        follow_redirects=True,
    )
    assert b"redirect added successfully" in response.data.lower()


def test_duplicate_redirect(client):
    login(client, "admin", "admin")
    client.post(
        "/admin",
        data={"source": "duplicate", "destination": "http://example.com"},
        follow_redirects=True,
    )
    response = client.post(
        "/admin",
        data={"source": "duplicate", "destination": "http://example.org"},
        follow_redirects=True,
    )
    assert b"source url already exists" in response.data.lower()


def test_delete_redirect(client):
    login(client, "admin", "admin")
    client.post(
        "/admin",
        data={"source": "todelete", "destination": "http://delete.com"},
        follow_redirects=True,
    )
    with client.application.app_context():
        Redirects = client.application.Redirects
        entry = Redirects.query.filter_by(source="todelete").first()
        assert entry is not None
        redirect_id = entry.id
    response = client.post(f"/delete/{redirect_id}", follow_redirects=True)
    json_data = response.get_json()
    assert json_data["success"] is True


def test_settings_update(client):
    login(client, "admin", "admin")
    response = client.post(
        "/settings",
        data={"username": "newadmin", "password": "newpassword", "dark_mode": "on"},
        follow_redirects=True,
    )
    assert b"settings updated successfully" in response.data.lower()
    with client.application.app_context():
        User = client.application.User
        user = User.query.filter_by(username="newadmin").first()
        assert user is not None
        assert user.dark_mode is True


def test_toggle_dark_mode(client):
    login(client, "admin", "admin")
    with client.application.app_context():
        User = client.application.User
        user = User.query.filter_by(username="admin").first()
        original_dark_mode = user.dark_mode
    response = client.post("/toggle_dark_mode", follow_redirects=True)
    json_data = response.get_json()
    assert json_data["success"] is True
    with client.application.app_context():
        User = client.application.User
        user = User.query.filter_by(username="admin").first()
        assert user.dark_mode != original_dark_mode


def test_dynamic_redirect(client):
    login(client, "admin", "admin")
    client.post(
        "/admin",
        data={"source": "dynamic", "destination": "http://dynamic.com"},
        follow_redirects=True,
    )
    response = client.get("/dynamic", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "http://dynamic.com"
