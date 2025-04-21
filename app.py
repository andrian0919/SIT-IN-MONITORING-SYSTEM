from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from flask import session
from flask import jsonify
from flask_mail import Mail, Message
import random
import string
import pandas as pd
from sqlalchemy import func
import os
from reports import generate_purpose_report, generate_year_level_report
from database import db
from sqlalchemy import text
from flask_wtf.csrf import generate_csrf
import threading
import time
import io
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle


app = Flask(__name__, instance_path=os.path.join(os.getcwd(), "SQLITE"), instance_relative_config=True)
app.secret_key = "sysarch32"
app.permanent_session_lifetime = timedelta(days=7)

# Configure mail for forgot password functionality
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-email-password'
mail = Mail(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sit_in_monitoring.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Make sure the database directory exists
os.makedirs(app.instance_path, exist_ok=True)

# Initialize the database with the app
db.init_app(app)

REPORTS_DIR = os.path.join("static", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Define the User model
class User(db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    firstname = db.Column(db.String(50), nullable=False)
    middlename = db.Column(db.String(50))
    course = db.Column(db.String(50), nullable=True) 
    yearlevel = db.Column(db.String(20), nullable=True) 
    role = db.Column(db.String(20), nullable=False, default="student")
    date_registered = db.Column(db.DateTime, default=datetime.utcnow) 
    password_reset_token = db.Column(db.String(50), nullable=True)  # Added for password reset functionality


# Define the Sessions model
class SessionRecord(db.Model):
    __tablename__ = "Sessions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    remaining_sessions = db.Column(db.Integer, nullable=False, default=30)  # Default to 10 sessions
    lab_usage_points = db.Column(db.Integer, nullable=False, default=0)  # Points that convert to sessions

class Reservation(db.Model):
    __tablename__ = "Reservation"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), db.ForeignKey("Users.student_id"), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)  # Added column for lastname
    firstname = db.Column(db.String(50), nullable=False)  # Added column for firstname
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    purpose = db.Column(db.String(100), nullable=False)
    lab = db.Column(db.String(50), nullable=False)
    available_pc = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default="Pending")
    time_in = db.Column(db.String(20), nullable=True)
    time_out = db.Column(db.String(20), nullable=True)

    student = db.relationship("User", backref="reservations")


class Lab(db.Model):
    __tablename__ = "Labs"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lab_name = db.Column(db.String(50), nullable=False)

class PC(db.Model):
    __tablename__ = "PCs"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lab_id = db.Column(db.Integer, db.ForeignKey("Labs.id"), nullable=False)
    pc_name = db.Column(db.String(50), nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)

class Announcement(db.Model):
    __tablename__ = "Announcements"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    announcement_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = "Feedback"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), nullable=False)
    lab = db.Column(db.String(50), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

    fixed_accounts = [
        {"student_id": "admin", "password": "admin123", "email": "admin@example.com", "lastname": "Admin", "firstname": "User", "role": "admin"},
        {"student_id": "staff", "password": "staff123", "email": "staff@example.com", "lastname": "Staff", "firstname": "User", "role": "staff"},
    ]

    for account in fixed_accounts:
        existing_user = User.query.filter_by(student_id=account["student_id"]).first()
        if not existing_user:
            new_user = User(
                student_id=account["student_id"],
                password=account["password"],  # Hash this for security
                email=account["email"],
                lastname=account["lastname"],
                firstname=account["firstname"],
                role=account["role"],
            )
            db.session.add(new_user)

    db.session.commit()

    # Add labs if they don't exist
    labs = ["524", "544", "523", "526", "Mac lab"]
    for lab_name in labs:
        existing_lab = Lab.query.filter_by(lab_name=lab_name).first()
        if not existing_lab:
            new_lab = Lab(lab_name=lab_name)
            db.session.add(new_lab)
            print(f"Added lab: {lab_name}")

    db.session.commit()
    
    # Add PCs for each lab
    labs_from_db = Lab.query.all()
    for lab in labs_from_db:
        # Check if this lab already has PCs
        existing_pcs = PC.query.filter_by(lab_id=lab.id).count()
        if existing_pcs == 0:
            # Number of PCs based on lab
            pc_count = 50  # Updated to 50 for all labs
            
            # Add PCs for each lab
            for i in range(1, pc_count + 1):
                pc_name = f"PC-{i}"
                new_pc = PC(lab_id=lab.id, pc_name=pc_name, is_available=True)
                db.session.add(new_pc)
                print(f"Added PC: {pc_name} to {lab.lab_name}")
    
    db.session.commit()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        student_id = request.form.get("username")
        password = request.form.get("password")
        remember_me = 'remember_me' in request.form

        user = User.query.filter_by(student_id=student_id).first()
        if user and user.password == password:
            session["user_id"] = user.id
            session["role"] = user.role  # Store role in session
            
            if remember_me:
                session.permanent = True  # Session lasts longer if 'Remember Me' is checked

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user.role == "staff":
                return redirect(url_for("staff_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            flash("Invalid ID or password", "error")
            return redirect(url_for("home"))

    return render_template("index.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate random token for password reset
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            user.password_reset_token = token
            db.session.commit()

            # Send the token via email
            msg = Message("Password Reset Request", sender="your-email@gmail.com", recipients=[email])
            msg.body = f"Your password reset token is: {token}"
            mail.send(msg)

            flash("Password reset token sent to your email.", "success")
            return redirect(url_for("home"))
        else:
            flash("Email not found!", "error")
            return redirect(url_for("home"))

    return render_template("forgot_password.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))

    # Get total number of registered students
    total_students = User.query.filter_by(role="student").count()

    # Get number of current sit-ins
    current_sit_in_count = Reservation.query.filter_by(status="Sit-in").count()

    # Get total number of completed sit-ins (include both Ended and Archived for cumulative stats)
    total_sit_ins = Reservation.query.filter(Reservation.status.in_(["Ended", "Archived"])).count()

    # Fetch active sessions with Purpose, Lab, and Status
    active_sessions = (
        db.session.query(
            User.student_id,
            User.firstname,
            User.lastname,
            Reservation.purpose,
            Reservation.lab,
            Reservation.status,
            SessionRecord.remaining_sessions
        )
        .join(SessionRecord, User.id == SessionRecord.user_id)
        .join(Reservation, User.student_id == Reservation.student_id)
        .filter(Reservation.status == "Approved")
        .all()
    )

    # Fetch all students
    all_students = (
        db.session.query(
            User.student_id,
            User.firstname,
            User.lastname,
            User.yearlevel,
            User.course,
            SessionRecord.remaining_sessions,
            SessionRecord.lab_usage_points,
            User.date_registered
        )
        .outerjoin(SessionRecord, User.id == SessionRecord.user_id)
        .filter(User.role == "student")  # Only include student users, not admin or staff
        .all()
    )

    # Fetch current sit-ins
    current_sit_ins = (
        db.session.query(
            Reservation.id,
            User.student_id,
            User.firstname,
            User.lastname,
            Reservation.purpose,
            Reservation.lab,
            Reservation.time_in,
            Reservation.status,
            SessionRecord.remaining_sessions
        )
        .join(User, User.student_id == Reservation.student_id)
        .join(SessionRecord, User.id == SessionRecord.user_id)
        .filter(Reservation.status == "Sit-in")
        .all()
    )

    # Fetch sit-in records for the current day only
    current_date = datetime.now().strftime("%Y-%m-%d")
    sit_in_records = (
        db.session.query(
            Reservation.id,
            User.student_id,
            User.firstname,
            User.lastname,
            Reservation.purpose,
            Reservation.lab,
            Reservation.time_in,
            Reservation.time_out,
            Reservation.date
        )
        .join(User, User.student_id == Reservation.student_id)
        .filter(Reservation.status == "Ended")
        .filter(Reservation.date == current_date)  # Only show today's records
        .all()
    )

    # Fetch pending reservations
    pending_reservations = (
        db.session.query(
            Reservation.id,
            User.student_id,
            User.firstname,
            User.lastname,
            Reservation.lab,
            Reservation.purpose,
            Reservation.date,
            Reservation.time
        )
        .join(User, User.student_id == Reservation.student_id)
        .filter(Reservation.status == "Pending")  # Only show pending reservations
        .all()
    )

    # Calculate Purpose statistics for chart - include both Ended and Archived for cumulative stats
    purpose_stats = (
        db.session.query(
            Reservation.purpose,
            func.count(Reservation.id).label("count")
        )
        .filter(Reservation.status.in_(["Ended", "Archived", "Sit-in"]))  # Include archived records for cumulative stats
        .group_by(Reservation.purpose)
        .all()
    )
    
    # Format purpose stats for JSON
    purpose_stats_list = [{"purpose": p.purpose, "count": p.count} for p in purpose_stats]
    
    # Calculate Lab statistics for chart - include both Ended and Archived for cumulative stats
    lab_stats = (
        db.session.query(
            Reservation.lab,
            func.count(Reservation.id).label("count")
        )
        .filter(Reservation.status.in_(["Ended", "Archived", "Sit-in"]))  # Include archived records for cumulative stats
        .group_by(Reservation.lab)
        .all()
    )
    
    # Format lab stats for JSON
    lab_stats_list = [{"lab": l.lab, "count": l.count} for l in lab_stats]

    # Fetch top 5 most active students (most sit-ins)
    top_students = (
        db.session.query(
            User.student_id,
            User.firstname,
            User.lastname,
            User.course,
            func.count(Reservation.id).label("sit_in_count")
        )
        .join(Reservation, User.student_id == Reservation.student_id)
        .filter(Reservation.status.in_(["Ended", "Archived", "Sit-in"]))
        .group_by(User.student_id, User.firstname, User.lastname, User.course)
        .order_by(func.count(Reservation.id).desc())
        .limit(5)
        .all()
    )
    
    # Format top students for the template
    top_students_list = [
        {
            "student_id": s.student_id,
            "name": f"{s.firstname} {s.lastname}",
            "course": s.course,
            "sit_in_count": s.sit_in_count
        } for s in top_students
    ]

    # Fetch report data
    report_data = (
        db.session.query(User.yearlevel, Reservation.purpose, func.count(Reservation.id).label("count"))
        .join(User, User.student_id == Reservation.student_id)
        .group_by(User.yearlevel, Reservation.purpose)
        .all()
    )

    # Fetch feedback data
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()

    return render_template(
        "admin_dashboard.html",
        all_students=all_students,
        current_sit_ins=current_sit_ins,
        sit_in_records=sit_in_records,
        active_sessions=active_sessions,
        report_data=report_data,
        feedbacks=feedbacks,  # Pass feedback data to the template
        purpose_stats=purpose_stats_list,  # Pass purpose statistics data
        lab_stats=lab_stats_list,  # Pass lab statistics data
        top_students=top_students_list,  # Pass top students leaderboard data
        total_students=total_students,
        current_sit_in_count=current_sit_in_count,
        total_sit_ins=total_sit_ins
    )

@app.route('/download_report/<report_type>')
def download_report(report_type):
    filename = f"report_{report_type}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)

    if report_type == "purpose":
        data = (
            db.session.query(Reservation.purpose, func.count(Reservation.id).label("count"))
            .group_by(Reservation.purpose)
            .all()
        )
        df = pd.DataFrame(data, columns=["Purpose", "Count"])

    elif report_type == "year_level":
        data = (
            db.session.query(User.yearlevel, func.count(User.id).label("count"))
            .group_by(User.yearlevel)
            .all()
        )
        df = pd.DataFrame(data, columns=["Year Level", "Count"])

    else:
        return jsonify({"error": "Invalid report type"}), 400

    df.to_excel(file_path, index=False)
    return jsonify({"file_url": f"/reports/{filename}", "file_name": filename})

@app.route('/reports/<filename>')
def serve_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)

@app.route("/staff_dashboard")
def staff_dashboard():
    if "user_id" not in session or session.get("role") != "staff":
        flash("Access denied!", "error")
        return redirect(url_for("home"))
    return render_template("staff_dashboard.html")


@app.route("/register", methods=["POST"])
def register():
    try:
        student_id = request.form.get("id")
        password = request.form.get("password")
        repeat_password = request.form.get("repeat_password")

        if password != repeat_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for("home"))

        existing_user = User.query.filter_by(student_id=student_id).first()
        if existing_user:
            flash("Student ID already exists!", "error")
            return redirect(url_for("home"))

        new_user = User(
            student_id=student_id,
            password=password,  # You should hash this for security
            email=request.form.get("email"),
            lastname=request.form.get("lastname"),
            firstname=request.form.get("firstname"),
            middlename=request.form.get("middlename"),
            course=request.form.get("course"),
            yearlevel=request.form.get("yearlevel"),
        )

        db.session.add(new_user)
        db.session.commit()

        # Set remaining sessions based on the course
        if new_user.course in ["BSIT", "BSCS"]:
            remaining_sessions = 30
        else:
            remaining_sessions = 15

        session_record = SessionRecord(user_id=new_user.id, remaining_sessions=remaining_sessions)
        db.session.add(session_record)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("home"))  # Redirect to login page

    except IntegrityError as e:
        db.session.rollback()
        flash("Email or student ID already exists", "error")
        return redirect(url_for("home"))


@app.route("/success")
def success():
    if "user_id" not in session:
        flash("Please log in first!", "error")
        return redirect(url_for("home"))
    
    user = User.query.get(session["user_id"])
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("home"))
        
    # Get remaining sessions
    session_record = SessionRecord.query.filter_by(user_id=session["user_id"]).first()
    remaining_sessions = session_record.remaining_sessions if session_record else 0
    
    # Add profile picture
    uploads_folder = os.path.join("static", "uploads")
    available_images = [f for f in os.listdir(uploads_folder) if f.endswith((".png", ".jpg"))]
    
    if available_images:
        profile_pic_filename = random.choice(available_images)
    else:
        profile_pic_filename = "default.png"
    
    profile_pic_url = url_for('static', filename=f'uploads/{profile_pic_filename}')
    
    return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, profile_pic=profile_pic_url)

@app.route("/student_dashboard")
def student_dashboard():
    if "user_id" not in session:
        flash("Please log in first!", "error")
        return redirect(url_for("home"))
    
    user = User.query.get(session["user_id"])
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("home"))

    session_record = SessionRecord.query.filter_by(user_id=session["user_id"]).first()
    remaining_sessions = session_record.remaining_sessions if session_record else 0

    # Define the uploads folder path
    uploads_folder = os.path.join("static", "uploads")

    # Get all available image files (.png and .jpg)
    available_images = [f for f in os.listdir(uploads_folder) if f.endswith((".png", ".jpg"))]

    # If images exist, randomly select one. Otherwise, use default.
    if available_images:
        profile_pic_filename = random.choice(available_images)
    else:
        profile_pic_filename = "default.png"

    profile_pic_url = url_for('static', filename=f'uploads/{profile_pic_filename}')

    return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, profile_pic=profile_pic_url)

@app.route('/static/<path:filename>')
def serve_uploads(filename):
    return send_from_directory('static/uploads', filename)


@app.route("/history")
def history():
    if "user_id" not in session:
        flash("Please log in first!", "error")
        return redirect(url_for("home"))

    user = User.query.get(session["user_id"])
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("home"))

    # Fetch reservation history for the student
    reservations = Reservation.query.filter_by(student_id=user.student_id).all()

    # Get remaining sessions for each student in reservations
    student_ids = [res.student_id for res in reservations]
    session_records = SessionRecord.query.filter(SessionRecord.user_id.in_(
        db.session.query(User.id).filter(User.student_id.in_(student_ids))
    )).all()

    # Create a dictionary to map student_id to remaining sessions
    remaining_sessions = {user.student_id: session.remaining_sessions for session in session_records for user in User.query.filter_by(id=session.user_id)}

    return render_template("history.html", user=user, reservations=reservations, remaining_sessions=remaining_sessions)

@app.route("/edit_record", methods=["GET", "POST"])
def edit_record():
    if "user_id" not in session:
        flash("Please log in first!", "error")
        return redirect(url_for("home"))

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        user.lastname = request.form.get("lastname", user.lastname)
        user.firstname = request.form.get("firstname", user.firstname)
        user.course = request.form.get("course", user.course)
        user.yearlevel = request.form.get("yearlevel", user.yearlevel)

        db.session.commit()

        # 🔹 **Fix Remaining Sessions Disappearing**
        session_record = SessionRecord.query.filter_by(user_id=session["user_id"]).first()
        remaining_sessions = session_record.remaining_sessions if session_record else 0

        # 🔹 **Fix Profile Picture Disappearing**
        uploads_folder = os.path.join("static", "uploads")
        available_images = [f for f in os.listdir(uploads_folder) if f.endswith((".png", ".jpg"))]

        if available_images:
            profile_pic_filename = random.choice(available_images)  # Random profile pic per login
        else:
            profile_pic_filename = "default.png"

        profile_pic_url = url_for('static', filename=f'uploads/{profile_pic_filename}')

        flash("Record updated successfully!", "success")

        # 🔹 **Return updated dashboard without pressing Home**
        return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, profile_pic=profile_pic_url)

    return render_template("edit_record.html", user=user)

@app.route("/view_sessions")
def view_sessions():
    if "user_id" not in session:
        return redirect(url_for("home"))

    session_record = SessionRecord.query.filter_by(user_id=session["user_id"]).first()
    remaining_sessions = session_record.remaining_sessions if session_record else 0

    return f"You have {remaining_sessions} remaining sessions."

@app.route("/get_available_pcs")
def get_available_pcs():
    lab_id = request.args.get("lab_id")

    if not lab_id:
        return jsonify([])

    try:
        lab_id = int(lab_id)  # Convert to integer
    except ValueError:
        return jsonify([])  # Return empty if invalid ID

    available_pcs = PC.query.filter_by(lab_id=lab_id, is_available=True).all()
    pcs_data = [{"id": pc.id, "pc_name": pc.pc_name} for pc in available_pcs]
    return jsonify(pcs_data)

@app.route("/make_reservation", methods=["GET", "POST"])
def make_reservation():
    if "user_id" not in session:
        flash("Please log in first!", "error")
        return redirect(url_for("home"))

    user = User.query.get(session["user_id"])
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("home"))

    session_record = SessionRecord.query.filter_by(user_id=session["user_id"]).first()
    remaining_sessions = session_record.remaining_sessions if session_record else 0
    labs = Lab.query.all()

    if request.method == "POST":
        date = request.form.get("date")
        time = request.form.get("time")
        purpose = request.form.get("purpose")
        lab_id = request.form.get("lab")
        pc_name = request.form.get("available_pc")  # Now getting PC name from dropdown

        lab = Lab.query.get(lab_id)
        if not lab:
            flash("Invalid laboratory selection!", "error")
            return redirect(url_for("make_reservation"))

        if not pc_name:
            flash("Please select a PC.", "error")
            return redirect(url_for("make_reservation"))

        # Mark the PC as unavailable
        pc = PC.query.filter_by(lab_id=lab.id, pc_name=pc_name).first()
        if pc:
            pc.is_available = False
            
        # Save reservation
        new_reservation = Reservation(
            student_id=user.student_id,
            lastname=user.lastname,
            firstname=user.firstname,
            date=date,
            time=time,
            purpose=purpose,
            lab=lab.lab_name,
            available_pc=pc_name,
            status="Pending"  # Default status
        )
        
        db.session.add(new_reservation)
        db.session.commit()
        flash("Reservation made successfully!", "success")
        return redirect(url_for("success"))

    return render_template(
        "make_reservation.html",
        user=user,
        remaining_sessions=remaining_sessions,
        labs=labs
    )

@app.route("/admin_reservations")
def admin_reservations():
    # First get pending reservations, then get others, and combine them
    pending_reservations = Reservation.query.filter_by(status="Pending").order_by(Reservation.id.desc()).all()
    other_reservations = Reservation.query.filter(Reservation.status != "Pending").all()
    
    # Combine lists to show pending reservations at top
    reservations = pending_reservations + other_reservations
    
    print("Fetched reservations:", reservations)  # Debugging
    return render_template("Reservation_Actions.html", reservations=reservations)


@app.route("/end_session/<student_id>", methods=["POST"])
def end_session(student_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    user = User.query.filter_by(student_id=student_id).first()
    if not user:
        return jsonify({"success": False, "error": "Student not found"}), 404

    session_record = SessionRecord.query.filter_by(user_id=user.id).first()
    if not session_record or session_record.remaining_sessions <= 0:
        return jsonify({"success": False, "error": "No remaining sessions"}), 400

    # Deduct one session
    session_record.remaining_sessions -= 1

    # Free up the PC
    latest_reservation = Reservation.query.filter_by(student_id=student_id).order_by(Reservation.id.desc()).first()
    if latest_reservation:
        pc = PC.query.filter_by(pc_name=latest_reservation.available_pc).first()
        if pc:
            pc.is_available = True  # Make the PC available again

    db.session.commit()

    return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

@app.route("/admin/post_announcement", methods=["POST"])
def post_announcement():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    announcement_text = request.form.get("announcement_text")
    if not announcement_text:
        return jsonify({"success": False, "error": "Announcement text is required"}), 400

    new_announcement = Announcement(announcement_text=announcement_text)
    db.session.add(new_announcement)
    db.session.commit()

    return jsonify({"success": True, "message": "Announcement posted successfully"})

@app.route("/get_announcements")
def get_announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    announcements_data = [{"id": ann.id, "text": ann.announcement_text, "created_at": ann.created_at} for ann in announcements]
    return jsonify(announcements_data)

@app.route("/edit_announcement/<int:id>", methods=["POST"])
def edit_announcement(id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    announcement = Announcement.query.get(id)
    if not announcement:
        return jsonify({"success": False, "error": "Announcement not found"}), 404

    new_text = request.json.get("text")
    if not new_text:
        return jsonify({"success": False, "error": "Announcement text is required"}), 400

    announcement.announcement_text = new_text
    db.session.commit()

    return jsonify({"success": True, "message": "Announcement updated successfully"})

@app.route("/delete_announcement/<int:id>", methods=["DELETE"])
def delete_announcement(id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    announcement = Announcement.query.get(id)
    if not announcement:
        return jsonify({"success": False, "error": "Announcement not found"}), 404

    db.session.delete(announcement)
    db.session.commit()

    return jsonify({"success": True, "message": "Announcement deleted successfully"})

@app.route("/announcements")
def announcements():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))

    return render_template("announcements.html")

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    student_id = data.get("student_id")
    feedback_text = data.get("feedback_text")
    lab = data.get("lab")
    
    # If lab is missing or Unknown, try to get it from the student's most recent reservation
    if not lab or lab == "Unknown":
        latest_reservation = Reservation.query.filter_by(
            student_id=student_id
        ).order_by(Reservation.id.desc()).first()
        
        if latest_reservation:
            lab = latest_reservation.lab
        else:
            lab = "Not Specified"

    if not student_id or not feedback_text:
        return jsonify({"success": False, "error": "Missing data"}), 400

    new_feedback = Feedback(
        student_id=student_id, 
        feedback_text=feedback_text,
        lab=lab
    )
    db.session.add(new_feedback)
    db.session.commit()

    return jsonify({"success": True, "message": "Feedback submitted successfully"})

@app.route("/feedback")
def feedback():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))

    feedbacks_with_users = db.session.query(
        Feedback.id,
        Feedback.student_id,
        Feedback.lab,
        Feedback.feedback_text,
        Feedback.created_at,
        User.firstname,
        User.lastname
    ).join(
        User, 
        Feedback.student_id == User.student_id
    ).order_by(Feedback.created_at.desc()).all()
    
    formatted_feedbacks = []
    for f in feedbacks_with_users:
        formatted_feedbacks.append({
            'id': f.id,
            'student_id': f.student_id,
            'firstname': f.firstname,
            'lastname': f.lastname,
            'lab': f.lab,
            'feedback_text': f.feedback_text,
            'created_at': f.created_at.strftime('%Y-%m-%d') if f.created_at else ''
        })

    return render_template("feedback.html", feedbacks=formatted_feedbacks)

@app.route("/reset_session/<student_id>", methods=["POST"])
def reset_session(student_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    user = User.query.filter_by(student_id=student_id).first()
    if not user:
        return jsonify({"success": False, "error": "Student not found"}), 404

    session_record = SessionRecord.query.filter_by(user_id=user.id).first()
    if not session_record:
        return jsonify({"success": False, "error": "Session record not found"}), 404

    # Reset the remaining sessions to the default value
    if user.course in ["BSIT", "BSCS"]:
        session_record.remaining_sessions = 30  # Default for BSIT and BSCS
    else:
        session_record.remaining_sessions = 15  # Default for other courses

    db.session.commit()

    return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

@app.route("/reset_all_sessions", methods=["POST"])
def reset_all_sessions():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        # Get all student users and their session records
        students = User.query.filter_by(role="student").all()
        
        for student in students:
            session_record = SessionRecord.query.filter_by(user_id=student.id).first()
            if session_record:
                # Reset based on course
                if student.course in ["BSIT", "BSCS"]:
                    session_record.remaining_sessions = 30
                else:
                    session_record.remaining_sessions = 15

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/sit_in/<student_id>", methods=["POST"])
def sit_in(student_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        # Get the request data
        data = request.get_json()
        purpose = data.get('purpose')
        lab = data.get('lab')

        user = User.query.filter_by(student_id=student_id).first()
        if not user:
            return jsonify({"success": False, "error": "Student not found"}), 404

        session_record = SessionRecord.query.filter_by(user_id=user.id).first()
        if not session_record or session_record.remaining_sessions <= 0:
            return jsonify({"success": False, "error": "No remaining sessions"}), 400

        # Check if student has an approved reservation
        reservation = Reservation.query.filter_by(student_id=student_id, status="Approved").first()
        
        if reservation:
            # Use the reservation's purpose and lab
            reservation.status = "Sit-in"
            reservation.time_in = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Create a new sit-in record
            new_reservation = Reservation(
                student_id=student_id,
                firstname=user.firstname,
                lastname=user.lastname,
                purpose=purpose,
                lab=lab,
                status="Sit-in",
                time_in=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                date=datetime.now().strftime("%Y-%m-%d"),
                time=datetime.now().strftime("%H:%M:%S"),
                available_pc="Not Assigned"  # Add default value for available_pc
            )
            db.session.add(new_reservation)

        db.session.commit()
        return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/end_sit_in/<int:sit_in_id>", methods=["POST"])
def end_sit_in(sit_in_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    reservation = Reservation.query.get(sit_in_id)
    if not reservation:
        return jsonify({"success": False, "error": "Sit-in session not found"}), 404

    # Get the user and their session record
    user = User.query.filter_by(student_id=reservation.student_id).first()
    if not user:
        return jsonify({"success": False, "error": "Student not found"}), 404

    session_record = SessionRecord.query.filter_by(user_id=user.id).first()
    if not session_record:
        return jsonify({"success": False, "error": "Session record not found"}), 404

    # Deduct one session when ending the sit-in
    if session_record.remaining_sessions > 0:
        session_record.remaining_sessions -= 1

    # Update the status to "Ended" and set the time-out
    reservation.status = "Ended"
    reservation.time_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()

    return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

@app.route("/update_status")
def update_status():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    reservations = Reservation.query.all()
    for reservation in reservations:
        reservation.status = "Active"  # Set default status
    db.session.commit()

    return jsonify({"success": True, "message": "Status updated successfully!"})

@app.route("/accept_reservation/<int:reservation_id>", methods=["POST"])
def accept_reservation(reservation_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    reservation = Reservation.query.get(reservation_id)
    if not reservation:
        return jsonify({"success": False, "error": "Reservation not found"}), 404

    # Update the reservation status to "Approved"
    reservation.status = "Approved"
    db.session.commit()

    return jsonify({"success": True})

@app.route("/decline_reservation/<int:reservation_id>", methods=["POST"])
def decline_reservation(reservation_id):
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    reservation = Reservation.query.get(reservation_id)
    if not reservation:
        return jsonify({"success": False, "error": "Reservation not found"}), 404

    # Update the reservation status to "Declined"
    reservation.status = "Declined"
    db.session.commit()

    return jsonify({"success": True})

@app.route('/Reservation_Actions')
def reservation_actions():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))
    
    # First get pending reservations, then get others, and combine them
    pending_reservations = Reservation.query.filter_by(status="Pending").order_by(Reservation.id.desc()).all()
    other_reservations = Reservation.query.filter(Reservation.status != "Pending").all()
    
    # Combine lists to show pending reservations at top
    reservations = pending_reservations + other_reservations
    
    return render_template("Reservation_Actions.html", reservations=reservations)

@app.after_request
def add_csrf_cookie(response):
    response.set_cookie("csrf_token", generate_csrf())
    return response

from datetime import datetime
from flask import session, jsonify

@app.route("/sit_in_reports")
def sit_in_reports():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))

    # Get filter parameters
    filter_type = request.args.get('filter_type', 'all')
    lab_filter = request.args.get('lab', '')
    purpose_filter = request.args.get('purpose', '')

    # Base query
    base_query = (
        db.session.query(
            Reservation.id,
            User.student_id,
            User.firstname,
            User.lastname,
            Reservation.purpose,
            Reservation.lab,
            Reservation.time_in,
            Reservation.time_out,
            Reservation.date
        )
        .join(User, User.student_id == Reservation.student_id)
        .filter(Reservation.status == "Ended")  # Only show Ended status, not Archived
    )
    
    # Apply filters based on the filter_type
    if filter_type == 'lab' and lab_filter:
        base_query = base_query.filter(Reservation.lab == lab_filter)
    elif filter_type == 'purpose' and purpose_filter:
        base_query = base_query.filter(Reservation.purpose == purpose_filter)
    
    # Execute query
    sit_in_records = base_query.all()

    # Get unique labs for the dropdown
    labs = db.session.query(Reservation.lab).distinct().order_by(Reservation.lab).all()
    labs = [lab[0] for lab in labs]
    
    # Get unique purposes for the dropdown
    purposes = db.session.query(Reservation.purpose).distinct().order_by(Reservation.purpose).all()
    purposes = [purpose[0] for purpose in purposes]

    return render_template(
        "sit_in_reports.html",
        sit_in_records=sit_in_records,
        labs=labs,
        purposes=purposes,
        filter_type=filter_type,
        selected_lab=lab_filter,
        selected_purpose=purpose_filter
    )

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("home"))

@app.route("/export_report", methods=["POST"])
def export_report():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    # Get data and format from the request
    data = request.json
    export_format = data.get("format")
    filter_type = data.get("filter_type", "all")
    filter_value = data.get("filter_value", "")
    get_all = data.get("get_all", False)
    
    # Create a filename based on the filter type
    if filter_type == "lab":
        prefix = f"lab_{filter_value}"
    elif filter_type == "purpose":
        prefix = f"purpose_{filter_value}"
    else:
        prefix = "sit_in"
    
    # If get_all is True, query the database for all records instead of using the data from the client
    if get_all:
        # Base query
        query = (
            db.session.query(
                User.student_id,
                db.func.concat(User.firstname, ' ', User.lastname).label("Full Name"),
                Reservation.purpose.label("Purpose"),
                Reservation.lab.label("Lab"),
                Reservation.time_in.label("Time-in"),
                Reservation.time_out.label("Time-out"),
                Reservation.date.label("Date")
            )
            .join(User, User.student_id == Reservation.student_id)
            .filter(Reservation.status == "Ended")
        )
        
        # Execute the query and convert to dict
        records = query.all()
        columns = ["ID", "Full Name", "Purpose", "Lab", "Time-in", "Time-out", "Date"]
        
        # Convert SQLAlchemy objects to dictionaries
        rows = []
        for record in records:
            row = {}
            for i, column in enumerate(columns):
                row[column] = str(record[i]) if record[i] is not None else ""
            rows.append(row)
            
        report_data = {"rows": rows}
    else:
        # Use the data provided by the client
        report_data = data.get("data")
    
    if not report_data or not export_format:
        return jsonify({"success": False, "error": "Missing data or format"}), 400
    
    # Create a DataFrame from the data
    df = pd.DataFrame(report_data["rows"])
    
    # Create a buffer to store the file
    buffer = io.BytesIO()
    
    # Export to the selected format
    if export_format == "csv":
        # Convert DataFrame to CSV
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        mimetype = "text/csv"
        filename = f"{prefix}_report.csv"
    
    elif export_format == "excel":
        # Convert DataFrame to Excel
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            sheet_name = "Records" if len(prefix) > 20 else f"{prefix} Records"
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            # Auto-adjust columns' width
            worksheet = writer.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_width)
        buffer.seek(0)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{prefix}_report.xlsx"
    
    elif export_format == "pdf":
        # Create a PDF using ReportLab
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        
        # Convert DataFrame to a list of lists for the table
        data_list = [df.columns.tolist()] + df.values.tolist()
        
        # Create the table
        table = Table(data_list)
        
        # Style the table
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        table.setStyle(style)
        elements.append(table)
        
        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        mimetype = "application/pdf"
        filename = f"{prefix}_report.pdf"
    
    else:
        return jsonify({"success": False, "error": "Invalid format"}), 400
    
    # Return the file as a response
    return send_file(
        buffer,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )

# Function to update the sit-in records at 9:30 PM
def archive_sit_in_records():
    with app.app_context():
        while True:
            now = datetime.now()
            
            # Check if it's 9:30 PM
            if now.hour == 21 and now.minute == 30:
                print("Running scheduled task: Archiving today's sit-in records...")
                
                # Get all active sit-in sessions
                active_sit_ins = Reservation.query.filter_by(status="Sit-in").all()
                
                # Update their status to "Ended" if they don't have a time_out
                for sit_in in active_sit_ins:
                    if not sit_in.time_out:
                        sit_in.status = "Ended"
                        sit_in.time_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Only archive today's Ended records, not all of them
                # This preserves the historical statistics for Student Statistics and Purpose counts
                current_date = datetime.now().strftime("%Y-%m-%d")
                todays_ended_reservations = Reservation.query.filter_by(
                    status="Ended", 
                    date=current_date
                ).all()
                
                for reservation in todays_ended_reservations:
                    reservation.status = "Archived"
                
                db.session.commit()
                print(f"Archived {len(active_sit_ins)} active sit-ins and {len(todays_ended_reservations)} today's records")
                
                # Wait until the next minute to avoid running the task multiple times
                time.sleep(60)
            else:
                # Check every minute
                time.sleep(60)

@app.route("/admin_dashboard/add_points", methods=["POST"])
def add_points():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    try:
        # Get data from either form data or JSON
        if request.form:
            student_id = request.form.get("student_id")
            points = int(request.form.get("points", 0))
        elif request.is_json:
            data = request.json
            student_id = data.get("student_id")
            points = int(data.get("points", 0))
        else:
            student_id = request.values.get("student_id")
            points = int(request.values.get("points", 0))
        
        # Log the received data for debugging
        print(f"Received add_points request: student_id={student_id}, points={points}")
        
        if not student_id or points <= 0:
            return jsonify({"success": False, "error": "Invalid student ID or points"}), 400
            
        # Find the user
        user = User.query.filter_by(student_id=student_id).first()
        if not user:
            return jsonify({"success": False, "error": "Student not found"}), 404
            
        # Find or create a session record for this user
        session_record = SessionRecord.query.filter_by(user_id=user.id).first()
        if not session_record:
            session_record = SessionRecord(user_id=user.id)
            db.session.add(session_record)
        
        # Store initial values for reporting
        initial_points = session_record.lab_usage_points
        initial_sessions = session_record.remaining_sessions
            
        # Add points to the user's record
        session_record.lab_usage_points += points
        
        # Convert points to sessions (3 points = 1 session)
        sessions_to_add = session_record.lab_usage_points // 3
        if sessions_to_add > 0:
            # Add the converted sessions
            session_record.remaining_sessions += sessions_to_add
            # Remove the used points (keep the remainder)
            session_record.lab_usage_points %= 3
            
        db.session.commit()
        
        # Calculate the changes for reporting
        points_change = session_record.lab_usage_points - initial_points + (sessions_to_add * 3)
        sessions_change = session_record.remaining_sessions - initial_sessions
        
        # Create a detailed message
        message = f"Added {points} points to student {student_id}."
        if sessions_change > 0:
            message += f" Converted {sessions_change * 3} points into {sessions_change} new sit-in sessions."
        
        # For form submissions that expect a redirect, handle that differently
        if request.headers.get('Accept') == 'text/html':
            flash(message, "success")
            return redirect(url_for("admin_dashboard"))
        
        return jsonify({
            "success": True, 
            "message": message,
            "points_added": points,
            "points_converted": sessions_change * 3,
            "sessions_added": sessions_change,
            "remaining_points": session_record.lab_usage_points,
            "remaining_sessions": session_record.remaining_sessions
        })
        
    except Exception as e:
        print(f"Error in add_points: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# Start the background thread for scheduled tasks
if __name__ == "__main__":
    # Create a daemon thread to run the scheduled task
    scheduler_thread = threading.Thread(target=archive_sit_in_records, daemon=True)
    scheduler_thread.start()
    
    app.run(debug=True, host="0.0.0.0",  port="5000")

@app.route("/update_feedback_labs", methods=["GET"])
def update_feedback_labs():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("home"))
        
    # Get all feedback records with Unknown lab
    unknown_feedbacks = Feedback.query.filter(
        (Feedback.lab == "Unknown") | (Feedback.lab == None)
    ).all()
    
    updated_count = 0
    
    for feedback in unknown_feedbacks:
        # Try to find a reservation for this student
        reservation = Reservation.query.filter_by(
            student_id=feedback.student_id
        ).order_by(Reservation.id.desc()).first()
        
        if reservation:
            feedback.lab = reservation.lab
            updated_count += 1
    
    db.session.commit()
    
    return f"Updated {updated_count} feedback records with correct lab information."
