from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# ================= CONFIG =================
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

DATABASE_URL = os.environ.get("DATABASE_URL")

# Render fix (postgres:// -> postgresql://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# fallback local
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///mentorhub.db"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

db = SQLAlchemy(app)

# ================= SUBJECTS =================
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
    mentor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    rating = db.Column(db.Integer)
    text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProofDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    filename = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ================= INIT DB (SAFE FOR RENDER) =================
def init_db():
    with app.app_context():
        db.create_all()
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

init_db()

# ================= HELPERS =================
def save_file(file):
    if not file or file.filename == "":
        return ""

    filename = secure_filename(file.filename)
    filename = f"{datetime.utcnow().timestamp()}_{filename}"

    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    return filename


def current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


@app.context_processor
def inject_globals():
    return dict(current_user=current_user(), subjects_list=SUBJECTS)

# ================= ROUTES =================
@app.route("/")
def index():
    mentors = User.query.filter_by(is_mentor=True).order_by(User.rating.desc()).limit(4).all()
    return render_template("index.html", mentors=mentors)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].lower()

        if User.query.filter_by(email=email).first():
            return "User already exists"

        user = User(
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            class_name=request.form["class_name"],
            email=email,
            password_hash=generate_password_hash(request.form["password"]),
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
        user = User.query.filter_by(email=request.form["email"]).first()

        if not user or not check_password_hash(user.password_hash, request.form["password"]):
            return "Invalid credentials"

        session["user_id"] = user.id
        return redirect(url_for("profile", user_id=user.id))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/profile/<int:user_id>")
def profile(user_id):
    user = User.query.get_or_404(user_id)
    reviews = Review.query.filter_by(mentor_id=user.id).all()
    return render_template("profile.html", user=user, reviews=reviews)

# ================= REQUIRED FOR RENDER =================
# NO app.run()
