
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# ================= CONFIG =================
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mentorhub-secret-key")

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    database_url = "sqlite:///mentorhub.db"

# fix for Render postgres:// → postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

db = SQLAlchemy(app)

# ================= INIT =================
with app.app_context():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()

# ================= DATA =================
SUBJECTS = [
    "Математика", "Алгебра", "Геометрия",
    "Физика", "Химия", "Биология",
    "География", "История", "Информатика",
    "Английский язык", "Русский язык", "Литература",
    "Казахский язык"
]

# ================= MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)

    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)

    photo = db.Column(db.String(250), default="")

    subjects = db.Column(db.Text, default="")
    grades = db.Column(db.Text, default="")
    about = db.Column(db.Text, default="")

    is_mentor = db.Column(db.Boolean, default=False)
    is_free = db.Column(db.Boolean, default=True)
    price = db.Column(db.Integer, default=0)
    available_time = db.Column(db.Text, default="")
    whatsapp = db.Column(db.String(100), default="")

    rating = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    mentor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProofDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    filename = db.Column(db.String(250), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship(
        "User",
        backref=db.backref("proof_documents", lazy=True, cascade="all, delete-orphan")
    )

# ================= HELPERS =================
def save_file(file):
    if not file or file.filename == "":
        return ""

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{filename}"

    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return filename


def save_multiple_files(files):
    return [save_file(f) for f in files if f and f.filename]


def current_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


@app.context_processor
def inject_user():
    return dict(current_user=current_user(), subjects_list=SUBJECTS)

# ================= ROUTES =================
@app.route("/")
def index():
    mentors = (
        User.query
        .filter_by(is_mentor=True)
        .order_by(User.rating.desc())
        .limit(4)
        .all()
    )
    return render_template("index.html", mentors=mentors)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("profile", user_id=current_user().id))

    if request.method == "POST":
        email = request.form.get("email").lower().strip()
        password = request.form.get("password").strip()

        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="Email already exists")

        user = User(
            first_name=request.form.get("first_name"),
            last_name=request.form.get("last_name"),
            class_name=request.form.get("class_name"),
            email=email,
            password_hash=generate_password_hash(password),
            photo=save_file(request.files.get("photo")),
            subjects=", ".join(request.form.getlist("subjects")),
            about=request.form.get("about", "")
        )

        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        return redirect(url_for("profile", user_id=user.id))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email")).first()

        if not user or not check_password_hash(user.password_hash, request.form.get("password")):
            return render_template("login.html", error="Wrong credentials")

        session["user_id"] = user.id
        return redirect(url_for("profile", user_id=user.id))

    return render_template("login.html")


@app.route("/profile/<int:user_id>")
def profile(user_id):
    user = User.query.get_or_404(user_id)
    reviews = Review.query.filter_by(mentor_id=user.id).all()
    return render_template("profile.html", user=user, reviews=reviews)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ================= IMPORTANT =================
# NO app.run() HERE — gunicorn handles it!

