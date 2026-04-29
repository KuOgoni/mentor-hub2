from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mentorhub-secret-key")

database_url = os.environ.get("DATABASE_URL", "sqlite:///mentorhub.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")

db = SQLAlchemy(app)

# СОЗДАНИЕ ТАБЛИЦ ПРИ ЗАПУСКЕ
with app.app_context():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()

SUBJECTS = [
    "Математика", "Алгебра", "Геометрия",
    "Физика", "Химия", "Биология",
    "География", "История", "Информатика",
    "Английский язык", "Русский язык", "Литература",
    "Казахский язык"
]


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
        backref=db.backref(
            "proof_documents",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )


def save_file(file):
    if not file or file.filename == "":
        return ""

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{filename}"

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    return filename


def save_multiple_files(files):
    saved_files = []

    for file in files:
        if file and file.filename:
            filename = save_file(file)
            if filename:
                saved_files.append(filename)

    return saved_files


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.get(user_id)


@app.context_processor
def inject_user():
    return dict(
        current_user=current_user(),
        subjects_list=SUBJECTS
    )


@app.route("/")
def index():
    mentors = (
        User.query
        .filter_by(is_mentor=True)
        .order_by(User.rating.desc(), User.created_at.asc())
        .limit(4)
        .all()
    )

    return render_template("index.html", mentors=mentors)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("profile", user_id=current_user().id))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if User.query.filter_by(email=email).first():
            return render_template(
                "register.html",
                error="Этот email уже зарегистрирован. Войдите в аккаунт или используйте другой email."
            )

        selected_subjects = request.form.getlist("subjects")
        grades_list = []

        for subject in selected_subjects:
            grade = request.form.get(f"grade_{subject}", "").strip()
            if grade:
                grades_list.append(f"{subject}: {grade}")

        user = User(
            first_name=request.form.get("first_name", "").strip(),
            last_name=request.form.get("last_name", "").strip(),
            class_name=request.form.get("class_name", "").strip(),
            email=email,
            password_hash=generate_password_hash(password),
            photo=save_file(request.files.get("photo")),
            subjects=", ".join(selected_subjects),
            grades=", ".join(grades_list),
            about=request.form.get("about", "").strip()
        )

        db.session.add(user)
        db.session.commit()

        proof_files = save_multiple_files(request.files.getlist("proof_files"))

        for filename in proof_files:
            document = ProofDocument(
                user_id=user.id,
                filename=filename
            )
            db.session.add(document)

        db.session.commit()

        session["user_id"] = user.id

        return redirect(url_for("profile", user_id=user.id))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("profile", user_id=current_user().id))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            return render_template(
                "login.html",
                error="Неверный email или пароль."
            )

        session["user_id"] = user.id

        return redirect(url_for("profile", user_id=user.id))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/mentors")
def mentors():
    subject = request.args.get("subject", "").strip()
    price_type = request.args.get("price_type", "").strip()

    query = User.query.filter_by(is_mentor=True)

    if subject:
        query = query.filter(User.subjects.ilike(f"%{subject}%"))

    if price_type == "free":
        query = query.filter_by(is_free=True)

    if price_type == "paid":
        query = query.filter_by(is_free=False)

    mentors = query.order_by(User.rating.desc(), User.created_at.desc()).all()

    return render_template("mentors.html", mentors=mentors)


@app.route("/profile/<int:user_id>")
def profile(user_id):
    user = User.query.get_or_404(user_id)

    reviews = (
        Review.query
        .filter_by(mentor_id=user.id)
        .order_by(Review.created_at.desc())
        .all()
    )

    return render_template("profile.html", user=user, reviews=reviews)


@app.route("/edit-profile/<int:user_id>", methods=["GET", "POST"])
def edit_profile(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    if request.method == "POST":
        selected_subjects = request.form.getlist("subjects")

        old_grades = {}

        if user.grades:
            for item in user.grades.split(","):
                if ":" in item:
                    subject, grade = item.split(":", 1)
                    old_grades[subject.strip()] = grade.strip()

        grades_list = []

        for subject in selected_subjects:
            grade = request.form.get(f"grade_{subject}", "").strip()

            if not grade and subject in old_grades:
                grade = old_grades[subject]

            if grade:
                grades_list.append(f"{subject}: {grade}")

        new_photo = save_file(request.files.get("photo"))

        user.first_name = request.form.get("first_name", "").strip()
        user.last_name = request.form.get("last_name", "").strip()
        user.class_name = request.form.get("class_name", "").strip()
        user.about = request.form.get("about", "").strip()
        user.subjects = ", ".join(selected_subjects)
        user.grades = ", ".join(grades_list)

        if new_photo:
            user.photo = new_photo

        new_documents = save_multiple_files(request.files.getlist("proof_files"))

        for filename in new_documents:
            document = ProofDocument(
                user_id=user.id,
                filename=filename
            )
            db.session.add(document)

        db.session.commit()

        return redirect(url_for("profile", user_id=user.id))

    return render_template("edit_profile.html", user=user)


@app.route("/become-mentor/<int:user_id>", methods=["POST"])
def become_mentor(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    user.is_mentor = True
    user.available_time = request.form.get("available_time", "").strip()
    user.whatsapp = request.form.get("whatsapp", "").strip()

    price_type = request.form.get("price_type")

    if price_type == "free":
        user.is_free = True
        user.price = 0
    else:
        user.is_free = False
        user.price = int(request.form.get("price") or 0)

    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))


@app.route("/stop-mentor/<int:user_id>", methods=["POST"])
def stop_mentor(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    user.is_mentor = False

    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))


@app.route("/review/<int:mentor_id>", methods=["POST"])
def add_review(mentor_id):
    mentor = User.query.get_or_404(mentor_id)
    reviewer = current_user()

    if not reviewer:
        return redirect(url_for("login"))

    if reviewer.id == mentor.id:
        return redirect(url_for("profile", user_id=mentor.id))

    review = Review(
        mentor_id=mentor.id,
        reviewer_id=reviewer.id,
        rating=int(request.form.get("rating") or 5),
        text=request.form.get("text", "").strip()
    )

    db.session.add(review)
    db.session.commit()

    all_reviews = Review.query.filter_by(mentor_id=mentor.id).all()

    mentor.rating = round(
        sum(r.rating for r in all_reviews) / len(all_reviews),
        1
    ) if all_reviews else 0

    db.session.commit()

    return redirect(url_for("profile", user_id=mentor.id))


@app.route("/delete-profile/<int:user_id>", methods=["POST"])
def delete_profile(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    db.session.delete(user)
    db.session.commit()

    session.clear()

    return redirect(url_for("index"))


@app.route("/delete-document/<int:doc_id>", methods=["POST"])
def delete_document(doc_id):
    doc = ProofDocument.query.get_or_404(doc_id)
    user = current_user()

    if not user or user.id != doc.user_id:
        return redirect(url_for("login"))

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(doc)
    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))]


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
        backref=db.backref(
            "proof_documents",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )


def save_file(file):
    if not file or file.filename == "":
        return ""

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{filename}"

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    return filename


def save_multiple_files(files):
    saved_files = []

    for file in files:
        if file and file.filename:
            filename = save_file(file)
            if filename:
                saved_files.append(filename)

    return saved_files


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.get(user_id)


@app.context_processor
def inject_user():
    return dict(
        current_user=current_user(),
        subjects_list=SUBJECTS
    )


@app.route("/")
def index():
    mentors = (
        User.query
        .filter_by(is_mentor=True)
        .order_by(User.rating.desc(), User.created_at.asc())
        .limit(4)
        .all()
    )

    return render_template("index.html", mentors=mentors)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("profile", user_id=current_user().id))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if User.query.filter_by(email=email).first():
            return render_template(
                "register.html",
                error="Этот email уже зарегистрирован. Войдите в аккаунт или используйте другой email."
            )

        selected_subjects = request.form.getlist("subjects")
        grades_list = []

        for subject in selected_subjects:
            grade = request.form.get(f"grade_{subject}", "").strip()
            if grade:
                grades_list.append(f"{subject}: {grade}")

        user = User(
            first_name=request.form.get("first_name", "").strip(),
            last_name=request.form.get("last_name", "").strip(),
            class_name=request.form.get("class_name", "").strip(),
            email=email,
            password_hash=generate_password_hash(password),
            photo=save_file(request.files.get("photo")),
            subjects=", ".join(selected_subjects),
            grades=", ".join(grades_list),
            about=request.form.get("about", "").strip()
        )

        db.session.add(user)
        db.session.commit()

        proof_files = save_multiple_files(request.files.getlist("proof_files"))

        for filename in proof_files:
            document = ProofDocument(
                user_id=user.id,
                filename=filename
            )
            db.session.add(document)

        db.session.commit()

        session["user_id"] = user.id

        return redirect(url_for("profile", user_id=user.id))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("profile", user_id=current_user().id))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            return render_template(
                "login.html",
                error="Неверный email или пароль."
            )

        session["user_id"] = user.id

        return redirect(url_for("profile", user_id=user.id))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/mentors")
def mentors():
    subject = request.args.get("subject", "").strip()
    price_type = request.args.get("price_type", "").strip()

    query = User.query.filter_by(is_mentor=True)

    if subject:
        query = query.filter(User.subjects.ilike(f"%{subject}%"))

    if price_type == "free":
        query = query.filter_by(is_free=True)

    if price_type == "paid":
        query = query.filter_by(is_free=False)

    mentors = query.order_by(User.rating.desc(), User.created_at.desc()).all()

    return render_template("mentors.html", mentors=mentors)


@app.route("/profile/<int:user_id>")
def profile(user_id):
    user = User.query.get_or_404(user_id)

    reviews = (
        Review.query
        .filter_by(mentor_id=user.id)
        .order_by(Review.created_at.desc())
        .all()
    )

    return render_template("profile.html", user=user, reviews=reviews)


@app.route("/edit-profile/<int:user_id>", methods=["GET", "POST"])
def edit_profile(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    if request.method == "POST":
        selected_subjects = request.form.getlist("subjects")

        old_grades = {}

        if user.grades:
            for item in user.grades.split(","):
                if ":" in item:
                    subject, grade = item.split(":", 1)
                    old_grades[subject.strip()] = grade.strip()

        grades_list = []

        for subject in selected_subjects:
            grade = request.form.get(f"grade_{subject}", "").strip()

            if not grade and subject in old_grades:
                grade = old_grades[subject]

            if grade:
                grades_list.append(f"{subject}: {grade}")

        new_photo = save_file(request.files.get("photo"))

        user.first_name = request.form.get("first_name", "").strip()
        user.last_name = request.form.get("last_name", "").strip()
        user.class_name = request.form.get("class_name", "").strip()
        user.about = request.form.get("about", "").strip()
        user.subjects = ", ".join(selected_subjects)
        user.grades = ", ".join(grades_list)

        if new_photo:
            user.photo = new_photo

        new_documents = save_multiple_files(request.files.getlist("proof_files"))

        for filename in new_documents:
            document = ProofDocument(
                user_id=user.id,
                filename=filename
            )
            db.session.add(document)

        db.session.commit()

        return redirect(url_for("profile", user_id=user.id))

    return render_template("edit_profile.html", user=user)


@app.route("/become-mentor/<int:user_id>", methods=["POST"])
def become_mentor(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    user.is_mentor = True
    user.available_time = request.form.get("available_time", "").strip()
    user.whatsapp = request.form.get("whatsapp", "").strip()

    price_type = request.form.get("price_type")

    if price_type == "free":
        user.is_free = True
        user.price = 0
    else:
        user.is_free = False
        user.price = int(request.form.get("price") or 0)

    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))


@app.route("/stop-mentor/<int:user_id>", methods=["POST"])
def stop_mentor(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    user.is_mentor = False

    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))


@app.route("/review/<int:mentor_id>", methods=["POST"])
def add_review(mentor_id):
    mentor = User.query.get_or_404(mentor_id)
    reviewer = current_user()

    if not reviewer:
        return redirect(url_for("login"))

    if reviewer.id == mentor.id:
        return redirect(url_for("profile", user_id=mentor.id))

    review = Review(
        mentor_id=mentor.id,
        reviewer_id=reviewer.id,
        rating=int(request.form.get("rating") or 5),
        text=request.form.get("text", "").strip()
    )

    db.session.add(review)
    db.session.commit()

    all_reviews = Review.query.filter_by(mentor_id=mentor.id).all()

    mentor.rating = round(
        sum(r.rating for r in all_reviews) / len(all_reviews),
        1
    ) if all_reviews else 0

    db.session.commit()

    return redirect(url_for("profile", user_id=mentor.id))


@app.route("/delete-profile/<int:user_id>", methods=["POST"])
def delete_profile(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user() or current_user().id != user.id:
        return redirect(url_for("login"))

    db.session.delete(user)
    db.session.commit()

    session.clear()

    return redirect(url_for("index"))


@app.route("/delete-document/<int:doc_id>", methods=["POST"])
def delete_document(doc_id):
    doc = ProofDocument.query.get_or_404(doc_id)
    user = current_user()

    if not user or user.id != doc.user_id:
        return redirect(url_for("login"))

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(doc)
    db.session.commit()

    return redirect(url_for("profile", user_id=user.id))


# ==================== ЗАПУСК ДЛЯ RENDER ====================
if __name__ == "__main__":
    # Создаем папку для загрузок
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    # Создаем все таблицы в базе данных
    with app.app_context():
        db.create_all()
    
    # Берем порт из переменной окружения (Render дает PORT)
    port = int(os.environ.get("PORT", 5000))
    
    # Запускаем сервер (debug=False для продакшена)
    app.run(host="0.0.0.0", port=port, debug=False)
