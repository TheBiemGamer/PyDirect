from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


class Redirects(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(150), unique=True, nullable=False)
    destination = db.Column(db.String(300), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin"))
    next_page = request.args.get("next")
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(next_page) if next_page else redirect(url_for("admin"))
        flash("Invalid credentials", "danger")
    return render_template("login.html", next_page=next_page)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if request.method == "POST":
        source = request.form["source"].strip()
        destination = request.form["destination"].strip()
        if not source or not destination:
            flash("Fields cannot be empty", "danger")
        else:
            if Redirects.query.filter_by(source=source).first():
                flash("Source URL already exists!", "warning")
            else:
                new_redirect = Redirects(source=source, destination=destination)
                db.session.add(new_redirect)
                db.session.commit()
                flash("Redirect added successfully!", "success")
    redirects = Redirects.query.all()
    return render_template("admin.html", redirects=redirects)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_redirect(id):
    redirect_entry = Redirects.query.get(id)
    if redirect_entry:
        db.session.delete(redirect_entry)
        db.session.commit()
        flash("Redirect deleted!", "success")
    return jsonify(success=True)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        new_username = request.form["username"]
        new_password = request.form["password"]
        if new_username and new_password:
            user = User.query.get(current_user.id)
            user.username = new_username
            user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
            db.session.commit()
            flash("Admin credentials updated successfully!", "success")
    return render_template("settings.html")


@app.route("/<path:source>")
def dynamic_redirect(source):
    redirect_entry = Redirects.query.filter_by(source=source).first()
    if redirect_entry:
        return redirect(redirect_entry.destination, code=302)
    return "Redirect not found", 404


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        admin_user = User.query.first()
        if not admin_user:
            admin = User(
                username="admin",
                password=generate_password_hash("admin", method="pbkdf2:sha256"),
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
