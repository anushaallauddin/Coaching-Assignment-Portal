from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
from werkzeug.utils import secure_filename

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("DATABASE_URL loaded:", bool(os.environ.get("DATABASE_URL")))

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Secret key for login sessions
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "coaching_portal_secret_key_change_this"
)
# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
print("DATABASE:", app.config["SQLALCHEMY_DATABASE_URI"].split("@")[-1])
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# TEACHER MODEL
# =========================

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# =========================
# STUDENT MODEL
# =========================

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_code = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    assignments = db.relationship(
        "Assignment",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan"
    )


# =========================
# ASSIGNMENT MODEL
# =========================

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    deadline = db.Column(
        db.DateTime,
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    submissions = db.relationship(
    "Submission",
    backref="assignment",
    lazy=True,
    cascade="all, delete-orphan"
)

# =========================
# SUBMISSION MODEL
# =========================

class Submission(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    assignment_id = db.Column(
        db.Integer,
        db.ForeignKey("assignment.id"),
        nullable=False,
        unique=True
    )

    file_name = db.Column(
        db.String(255),
        nullable=False
    )

    file_path = db.Column(
        db.String(500),
        nullable=False
    )

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    is_late = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    marks = db.Column(
        db.Float,
        nullable=True
    )

    feedback = db.Column(
        db.Text,
        nullable=True
    )

# =========================
# CREATE DATABASE
# =========================

with app.app_context():
    db.create_all()

    # Create default teacher if one doesn't exist
    if not Teacher.query.first():
        teacher = Teacher(
            username="admin",
            password=generate_password_hash("admin123")
        )

        db.session.add(teacher)
        db.session.commit()


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return redirect(url_for("teacher_login"))


# =========================
# TEACHER LOGIN
# =========================

@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        teacher = Teacher.query.filter_by(username=username).first()

        if teacher and check_password_hash(teacher.password, password):

            session["teacher_id"] = teacher.id

            return redirect(url_for("teacher_dashboard"))

        else:
            return render_template(
                "login.html",
                error="Invalid username or password."
            )

    return render_template("login.html")


# =========================
# TEACHER DASHBOARD
# =========================

@app.route("/teacher/dashboard")
def teacher_dashboard():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    # Total students
    total_students = Student.query.count()

    # Total assignments
    total_assignments = Assignment.query.count()

    # Total submitted assignments
    submitted_count = Submission.query.count()

    # Pending assignments
    pending_count = total_assignments - submitted_count

    # Late submissions
    late_count = Submission.query.filter_by(
        is_late=True
    ).count()

    # Assignments that have been marked
    marked_count = Submission.query.filter(
        Submission.marks.isnot(None)
    ).count()

    return render_template(
        "teacher_dashboard.html",
        total_students=total_students,
        total_assignments=total_assignments,
        submitted_count=submitted_count,
        pending_count=pending_count,
        late_count=late_count,
        marked_count=marked_count
    )

# =========================
# ADD STUDENT
# =========================

@app.route("/teacher/add-student", methods=["GET", "POST"])
def add_student():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    if request.method == "POST":

        name = request.form["name"].strip()
        student_code = request.form["student_code"].strip()
        password = request.form["password"]

        # Check if student code already exists
        existing_student = Student.query.filter_by(
            student_code=student_code
        ).first()

        if existing_student:
            return render_template(
                "add_student.html",
                error="This student code already exists."
            )

        student = Student(
            name=name,
            student_code=student_code,
            password=generate_password_hash(password)
        )

        db.session.add(student)
        db.session.commit()

        return redirect(url_for("students"))

    return render_template("add_student.html")


# =========================
# VIEW STUDENTS
# =========================

@app.route("/teacher/students")
def students():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    all_students = Student.query.order_by(Student.id.desc()).all()

    return render_template(
        "students.html",
        students=all_students
    )

# =========================
# TEACHER LOGOUT
# =========================

@app.route("/teacher/logout")
def teacher_logout():

    session.pop("teacher_id", None)

    return redirect(url_for("teacher_login"))

# =========================
# STUDENT LOGIN
# =========================

@app.route("/student/login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        student_code = request.form["student_code"].strip()
        password = request.form["password"]

        student = Student.query.filter_by(
            student_code=student_code
        ).first()

        if student and check_password_hash(student.password, password):

            session["student_id"] = student.id

            return redirect(url_for("student_dashboard"))

        else:
            return render_template(
                "student_login.html",
                error="Invalid student code or password."
            )

    return render_template("student_login.html")


# =========================
# STUDENT DASHBOARD
# =========================

@app.route("/student/dashboard")
def student_dashboard():

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student = Student.query.get(session["student_id"])

    assignments = Assignment.query.filter_by(
        student_id=student.id
    ).order_by(
        Assignment.deadline.asc()
    ).all()

    return render_template(
        "student_dashboard.html",
        student=student,
        assignments=assignments
    )

# =========================
# SUBMIT ASSIGNMENT
# =========================

@app.route("/student/submit-assignment/<int:assignment_id>", methods=["POST"])
def submit_assignment(assignment_id):

    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student = Student.query.get(session["student_id"])

    assignment = Assignment.query.get_or_404(assignment_id)

    # Make sure this assignment belongs to the logged-in student
    if assignment.student_id != student.id:
        return "Unauthorized access", 403

    # Get uploaded file
    file = request.files.get("file")

    if not file or file.filename == "":
        return "Please select a file."

    # Check file extension
    original_filename = file.filename
    extension = original_filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        return "Only PDF and DOCX files are allowed."

    # Create a safe filename
    safe_filename = secure_filename(original_filename)

    # Add student and assignment ID to avoid filename conflicts
    filename = f"student_{student.id}_assignment_{assignment.id}_{safe_filename}"

    # Supabase Storage path
    storage_path = filename

    # Check if submission already exists
    submission = Submission.query.filter_by(
        assignment_id=assignment.id
    ).first()

    # Read uploaded file
    file_data = file.read()

    # If replacing an old submission
    if submission:

        old_storage_path = submission.file_path

        try:
            supabase.storage.from_("assignments").remove(
                [old_storage_path]
            )
        except Exception:
            pass

        # Upload new file to Supabase
        supabase.storage.from_("assignments").upload(
            storage_path,
            file_data,
            {
                "content-type": file.content_type
            }
        )

        submission.file_name = safe_filename
        submission.file_path = storage_path
        submission.submitted_at = datetime.utcnow()
        submission.is_late = datetime.utcnow() > assignment.deadline

    else:

        # Upload new file to Supabase
        supabase.storage.from_("assignments").upload(
            storage_path,
            file_data,
            {
                "content-type": file.content_type
            }
        )

        submission = Submission(
            assignment_id=assignment.id,
            file_name=safe_filename,
            file_path=storage_path,
            submitted_at=datetime.utcnow(),
            is_late=datetime.utcnow() > assignment.deadline
        )

        db.session.add(submission)

    db.session.commit()

    return redirect(url_for("student_dashboard"))
# =========================
# TEACHER SUBMISSIONS
# =========================

@app.route("/teacher/submissions")
def teacher_submissions():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    assignments = Assignment.query.order_by(
        Assignment.deadline.asc()
    ).all()

    return render_template(
        "submissions.html",
        assignments=assignments
    )

# =========================
# DOWNLOAD SUBMISSION
# =========================

@app.route("/teacher/download-submission/<int:submission_id>")
def download_submission(submission_id):

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    submission = Submission.query.get_or_404(submission_id)

    try:
        # Download file from Supabase Storage
        file_data = supabase.storage.from_("assignments").download(
            submission.file_path
        )

        # Send file to teacher's browser
        from io import BytesIO

        return send_file(
            BytesIO(file_data),
            as_attachment=True,
            download_name=submission.file_name
        )

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        return "File not found.", 404
    
# =========================
# MARK SUBMISSION
# =========================

@app.route("/teacher/mark-submission/<int:submission_id>", methods=["POST"])
def mark_submission(submission_id):

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    submission = Submission.query.get_or_404(submission_id)

    marks = request.form.get("marks", "").strip()
    feedback = request.form.get("feedback", "").strip()

    if marks == "":
        submission.marks = None
    else:
        try:
            submission.marks = float(marks)
        except ValueError:
            return "Invalid marks.", 400

    submission.feedback = feedback

    db.session.commit()

    return redirect(url_for("teacher_submissions"))

# =========================
# STUDENT LOGOUT
# =========================

@app.route("/student/logout")
def student_logout():

    session.pop("student_id", None)

    return redirect(url_for("student_login"))

# =========================
# CREATE ASSIGNMENT
# =========================
@app.route("/teacher/create-assignment", methods=["GET", "POST"])
def create_assignment():

    if "teacher_id" not in session:
        return redirect(url_for("teacher_login"))

    all_students = Student.query.order_by(Student.name).all()

    if request.method == "POST":

        title = request.form["title"].strip()
        description = request.form["description"].strip()
        deadline_string = request.form["deadline"]
        student_id = request.form["student_id"]

        deadline = datetime.strptime(
            deadline_string,
            "%Y-%m-%dT%H:%M"
        )

        # =========================
        # ASSIGN TO ALL STUDENTS
        # =========================

        if student_id == "all":

            for student in all_students:

                existing_assignment = Assignment.query.filter_by(
                    student_id=student.id
                ).first()

                if existing_assignment:
                    continue

                assignment = Assignment(
                    title=title,
                    description=description,
                    deadline=deadline,
                    student_id=student.id
                )

                db.session.add(assignment)

            db.session.commit()

            return redirect(url_for("teacher_dashboard"))

        # =========================
        # ASSIGN TO ONE STUDENT
        # =========================

        student_id = int(student_id)

        existing_assignment = Assignment.query.filter_by(
            student_id=student_id
        ).first()

        if existing_assignment:

            return render_template(
                "create_assignment.html",
                students=all_students,
                error="This student already has an assignment."
            )

        assignment = Assignment(
            title=title,
            description=description,
            deadline=deadline,
            student_id=student_id
        )

        db.session.add(assignment)
        db.session.commit()

        return redirect(url_for("teacher_dashboard"))

    return render_template(
        "create_assignment.html",
        students=all_students
    )
  
        
        

# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":
 app.run(debug=False)