from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from flask_wtf.csrf import generate_csrf
import uuid
import os
import secrets
import string
import csv
import io
import random
import json
import pandas as pd
from io import BytesIO
import tempfile
import re
import threading
import time
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask_caching import Cache
from database import db

app = Flask(__name__)

# Config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sit_in_monitoring.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "sit-in-monitoring-secret-key"
app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "static", "uploads")
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Setup mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # replace with your email
app.config['MAIL_PASSWORD'] = 'your-app-password'  # replace with app password

# Initialize extensions
mail = Mail(app)
db.init_app(app)
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})

REPORTS_DIR = os.path.join("static", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# SIMPLE, DIRECT RESOURCE ENABLE/DISABLE ROUTES 
# Put these at the top to ensure they're registered
@app.route("/direct_enable/<int:resource_id>")
def direct_enable_resource(resource_id):
    """Direct enable using simple SQL"""
    try:
        # Simple SQL update
        db.session.execute(db.text(f"UPDATE Resources SET status = 'enabled' WHERE id = {resource_id}"))
        db.session.commit()
        flash("Resource enabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/direct_disable/<int:resource_id>")
def direct_disable_resource(resource_id):
    """Direct disable using simple SQL"""
    try:
        # Simple SQL update
        db.session.execute(db.text(f"UPDATE Resources SET status = 'disabled' WHERE id = {resource_id}"))
        db.session.commit()
        flash("Resource disabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

# Helper function to get current user
def get_current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None

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

class LabSchedule(db.Model):
    __tablename__ = "LabSchedules"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lab_id = db.Column(db.Integer, db.ForeignKey("Labs.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    day_of_week = db.Column(db.String(20), nullable=False)  # e.g., Monday, Tuesday, etc.
    start_time = db.Column(db.String(20), nullable=False)  # e.g., "08:00"
    end_time = db.Column(db.String(20), nullable=False)  # e.g., "10:00" 
    max_capacity = db.Column(db.String(100), nullable=True)  # Changed from instructor to max_capacity
    course = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    lab = db.relationship("Lab", backref="schedules")

class Resource(db.Model):
    __tablename__ = "Resources"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # e.g., pdf, docx, pptx, etc.
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="enabled")  # enabled or disabled
    original_filename = db.Column(db.String(255), nullable=True)  # Store original filename
    
    user = db.relationship("User", backref="resources")

# Create tables if they don't exist
with app.app_context():
    try:
        # Check if Labs table exists, if not create it
        inspector = db.inspect(db.engine)
        if "Labs" not in inspector.get_table_names():
            print("Creating Labs table")
            # Create the Labs table
            db.Model.metadata.tables["Labs"].create(db.engine)
            print("Labs table created successfully")
            
            # Add labs if they don't exist
            labs = ["524", "544", "523", "526", "Mac lab"]
            for lab_name in labs:
                new_lab = Lab(lab_name=lab_name)
                db.session.add(new_lab)
                print(f"Added lab: {lab_name}")
            
            db.session.commit()
            print("Labs committed to database")
        
        # Check if PCs table exists, if not create it
        if "PCs" not in inspector.get_table_names():
            print("Creating PCs table")
            # Create the PCs table
            db.Model.metadata.tables["PCs"].create(db.engine)
            print("PCs table created successfully")
            
            # Add PCs for each lab
            labs_from_db = Lab.query.all()
            for lab in labs_from_db:
                # Number of PCs based on lab
                pc_count = 50  # Updated to 50 for all labs
                
                # Add PCs for each lab
                for i in range(1, pc_count + 1):
                    pc_name = f"PC-{i}"
                    new_pc = PC(lab_id=lab.id, pc_name=pc_name, is_available=True)
                    db.session.add(new_pc)
                    print(f"Added PC: {pc_name} to {lab.lab_name}")
            
            db.session.commit()
            print("PCs committed to database")
        
        # Check if LabSchedules table exists, if not create it
        if "LabSchedules" not in inspector.get_table_names():
            print("Creating LabSchedules table")
            # Create the LabSchedules table
            db.Model.metadata.tables["LabSchedules"].create(db.engine)
            print("LabSchedules table created successfully")
            db.session.commit()
            print("LabSchedules committed to database")
        else:
            # Check if the table has the required columns
            try:
                # Test query to check if the table has the required columns
                LabSchedule.query.first()
            except Exception as e:
                print(f"LabSchedules table schema appears incorrect: {str(e)}")
                print("Dropping and recreating LabSchedules table...")
                
                # Drop the existing table
                db.session.execute(text("DROP TABLE IF EXISTS LabSchedules"))
                db.session.commit()
                
                # Recreate the table
                db.Model.metadata.tables["LabSchedules"].create(db.engine)
                print("LabSchedules table recreated successfully")
                db.session.commit()
        
        # Check if Resources table exists, if not create it
        if "Resources" not in inspector.get_table_names():
            print("Creating Resources table")
            # Create the Resources table
            db.Model.metadata.tables["Resources"].create(db.engine)
            print("Resources table created successfully")
            db.session.commit()
            print("Resources table committed to database")
        else:
            # Check if the table has the required columns
            try:
                # Test query to check if the table has the required columns
                Resource.query.first()
            except Exception as e:
                print(f"Resources table schema appears incorrect: {str(e)}")
                print("Dropping and recreating Resources table...")
                
                # Drop the existing table
                from sqlalchemy import text
                db.session.execute(text("DROP TABLE IF EXISTS Resources"))
                db.session.commit()
                
                # Recreate the table
                db.Model.metadata.tables["Resources"].create(db.engine)
                print("Resources table recreated successfully")
                db.session.commit()
        
        # Create uploads/resources directory if it doesn't exist
        resources_dir = os.path.join(app.config["UPLOAD_FOLDER"], "resources")
        if not os.path.exists(resources_dir):
            os.makedirs(resources_dir)
            print(f"Created resources directory: {resources_dir}")
        
        # Create other tables that might not exist
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
    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        db.session.rollback()

@app.route("/")
def home():
    """Redirect to the appropriate dashboard based on user role or to login page."""
    # Clear any existing session to force login
    if "user_id" in session:
        session.pop("user_id", None)
        session.pop("role", None)
    
    # Display the login page
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    """Redirect to the appropriate dashboard based on user role."""
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        elif session.get("role") == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("student_dashboard"))
    else:
        # If no active session, redirect to login
        flash("Please log in first", "error")
        return redirect(url_for("home"))

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
            Reservation.available_pc,
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
            Reservation.available_pc,
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
            Reservation.available_pc,
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
            Reservation.available_pc,
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
            func.count(Reservation.id).label("sit_in_count"),
            SessionRecord.lab_usage_points
        )
        .join(Reservation, User.student_id == Reservation.student_id)
        .join(SessionRecord, SessionRecord.user_id == User.id)
        .filter(Reservation.status.in_(["Ended", "Archived", "Sit-in"]))
        .group_by(User.student_id, User.firstname, User.lastname, User.course, SessionRecord.lab_usage_points)
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
            "sit_in_count": s.sit_in_count,
            "reward_points": s.lab_usage_points
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
    
    # Fetch all labs for computer control dropdown
    all_labs = Lab.query.all()

    return render_template(
        "admin_dashboard.html",
        all_students=all_students,
        current_sit_ins=current_sit_ins,
        sit_in_records=sit_in_records,
        active_sessions=active_sessions,
        report_data=report_data,  # Pass report data to the template
        feedbacks=feedbacks,  # Pass feedback data to the template
        purpose_stats=purpose_stats_list,  # Pass purpose statistics data
        lab_stats=lab_stats_list,  # Pass lab statistics data
        top_students=top_students_list,  # Pass top students leaderboard data
        total_students=total_students,
        current_sit_in_count=current_sit_in_count,
        total_sit_ins=total_sit_ins,
        labs=all_labs  # Pass all labs for computer control dropdown
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
    lab_usage_points = session_record.lab_usage_points if session_record else 0
    
    # Add profile picture
    uploads_folder = os.path.join("static", "uploads")
    available_images = [f for f in os.listdir(uploads_folder) if f.endswith((".png", ".jpg"))]
    
    if available_images:
        profile_pic_filename = random.choice(available_images)
    else:
        profile_pic_filename = "default.png"
    
    profile_pic_url = url_for('static', filename=f'uploads/{profile_pic_filename}')
    
    return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, lab_usage_points=lab_usage_points, profile_pic=profile_pic_url)

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
    lab_usage_points = session_record.lab_usage_points if session_record else 0

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

    return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, lab_usage_points=lab_usage_points, profile_pic=profile_pic_url)

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
        lab_usage_points = session_record.lab_usage_points if session_record else 0

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
        return render_template("student_dashboard.html", user=user, remaining_sessions=remaining_sessions, lab_usage_points=lab_usage_points, profile_pic=profile_pic_url)

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

        # Check if PC is already reserved
        existing_reservation = Reservation.query.filter_by(
            lab=lab.lab_name,
            available_pc=pc_name,
            status="Pending"
        ).first()
        
        if existing_reservation:
            flash("This PC is already reserved. Please select another PC.", "error")
            return redirect(url_for("make_reservation"))

        # Mark the PC as unavailable
        pc = PC.query.filter_by(lab_id=lab.id, pc_name=pc_name).first()
        if pc:
            pc.is_available = False
        else:
            # If PC doesn't exist in the database yet, create it
            pc = PC(lab_id=lab.id, pc_name=pc_name, is_available=False)
            db.session.add(pc)
            
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
        available_pc = data.get('available_pc', "Not Assigned")  # Default to "Not Assigned" if not provided

        # Validate required fields
        if not purpose or not lab:
            return jsonify({"success": False, "error": "Purpose and lab are required"}), 400

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
            
            # Keep the originally assigned PC from the reservation if available_pc is not specified
            if available_pc == "Not Assigned" and reservation.available_pc and reservation.available_pc != "Not Assigned":
                # Keep using the PC that was assigned during reservation
                print(f"Using reserved PC: {reservation.available_pc} for student {student_id}")
            elif available_pc != "Not Assigned" and available_pc != reservation.available_pc:
                # If admin selected a different PC, update it
                # Free up the previously assigned PC if any
                if reservation.available_pc and reservation.available_pc != "Not Assigned":
                    old_lab = Lab.query.filter_by(lab_name=reservation.lab).first()
                    if old_lab:
                        old_pc = PC.query.filter_by(lab_id=old_lab.id, pc_name=reservation.available_pc).first()
                        if old_pc:
                            old_pc.is_available = True
                
                # Assign the new PC
                reservation.available_pc = available_pc
                
                # Mark the new PC as unavailable
                new_lab = Lab.query.filter_by(lab_name=reservation.lab).first()
                if new_lab and available_pc != "Not Assigned":
                    new_pc = PC.query.filter_by(lab_id=new_lab.id, pc_name=available_pc).first()
                    if new_pc:
                        new_pc.is_available = False
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
                available_pc=available_pc
            )
            db.session.add(new_reservation)
            
            # Mark the PC as unavailable
            if available_pc != "Not Assigned":
                lab_obj = Lab.query.filter_by(lab_name=lab).first()
                if lab_obj:
                    pc = PC.query.filter_by(lab_id=lab_obj.id, pc_name=available_pc).first()
                    if pc:
                        pc.is_available = False

        db.session.commit()
        return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

    except Exception as e:
        db.session.rollback()
        print(f"Error in sit_in: {str(e)}")
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

    # Free up the PC if it has been assigned
    if reservation.available_pc and reservation.available_pc != "Not Assigned":
        lab = Lab.query.filter_by(lab_name=reservation.lab).first()
        if lab:
            pc = PC.query.filter_by(lab_id=lab.id, pc_name=reservation.available_pc).first()
            if pc:
                pc.is_available = True

    # Update the status to "Ended" and set the time-out
    reservation.status = "Ended"
    reservation.time_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()

    return jsonify({"success": True, "remaining_sessions": session_record.remaining_sessions})

@app.route("/end_sit_in_with_points/<int:sit_in_id>", methods=["POST"])
def end_sit_in_with_points(sit_in_id):
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
    
    # Calculate sessions before adding point
    sessions_before = session_record.lab_usage_points // 3
        
    # Add 1 point to lab_usage_points
    session_record.lab_usage_points += 1
    
    # Calculate sessions after adding point
    sessions_after = session_record.lab_usage_points // 3
    
    # Check if we have added enough points to gain a new session
    sessions_to_add = sessions_after - sessions_before
    if sessions_to_add > 0:
        # Add the converted sessions
        session_record.remaining_sessions += sessions_to_add

    # Free up the PC if it has been assigned
    if reservation.available_pc and reservation.available_pc != "Not Assigned":
        lab = Lab.query.filter_by(lab_name=reservation.lab).first()
        if lab:
            pc = PC.query.filter_by(lab_id=lab.id, pc_name=reservation.available_pc).first()
            if pc:
                pc.is_available = True

    # Update the status to "Ended" and set the time-out
    reservation.status = "Ended"
    reservation.time_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()

    return jsonify({
        "success": True, 
        "remaining_sessions": session_record.remaining_sessions,
        "lab_usage_points": session_record.lab_usage_points
    })

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

    # Ensure the PC is marked as unavailable
    lab = Lab.query.filter_by(lab_name=reservation.lab).first()
    if lab:
        pc = PC.query.filter_by(lab_id=lab.id, pc_name=reservation.available_pc).first()
        if pc:
            pc.is_available = False
        else:
            # Create PC if it doesn't exist
            pc = PC(lab_id=lab.id, pc_name=reservation.available_pc, is_available=False)
            db.session.add(pc)

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

    # Free up the PC
    lab = Lab.query.filter_by(lab_name=reservation.lab).first()
    if lab:
        pc = PC.query.filter_by(lab_id=lab.id, pc_name=reservation.available_pc).first()
        if pc:
            pc.is_available = True

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
    # Clear all session data
    session.clear()
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
        # For CSV, we need to create it in memory
        header_lines = [
            "College of Computer Studies",
            "University of Cebu",
            "Sit-In Monitoring System Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""  # Empty line as separator
        ]
        
        # Create a string buffer
        csv_data = io.StringIO()
        
        # Write headers
        for line in header_lines:
            csv_data.write(line + "\n")
        
        # Write DataFrame as CSV
        df.to_csv(csv_data, index=False)
        
        # Get the string content and convert to bytes for the buffer
        csv_content = csv_data.getvalue().encode('utf-8')
        buffer.write(csv_content)
        
        # Rewind buffer to beginning
        buffer.seek(0)
        mimetype = "text/csv"
        filename = f"{prefix}_report.csv"
    
    elif export_format == "excel":
        # Convert DataFrame to Excel with header
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            sheet_name = "Records" if len(prefix) > 20 else f"{prefix} Records"
            
            # Write the header rows
            workbook = writer.book
            worksheet = workbook.add_worksheet(sheet_name)
            writer.sheets[sheet_name] = worksheet
            
            # Add formatting
            title_format = workbook.add_format({
                'bold': True, 
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter',
                'font_color': '#003366',  # Dark blue
                'top': 1,
                'left': 1,
                'right': 1
            })
            
            header_format = workbook.add_format({
                'bold': True, 
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter',
                'left': 1,
                'right': 1
            })
            
            subheader_format = workbook.add_format({
                'bold': False,
                'font_size': 12,
                'align': 'center',
                'valign': 'vcenter',
                'left': 1,
                'right': 1
            })
            
            date_format = workbook.add_format({
                'italic': True,
                'font_size': 10,
                'align': 'center',
                'bottom': 1,
                'left': 1,
                'right': 1
            })
            
            # Set column widths
            worksheet.set_column('A:G', 20)  # Set a default width for all columns
            
            # Write headers with merged cells and borders
            worksheet.merge_range('A1:G1', 'College of Computer Studies', title_format)
            worksheet.merge_range('A2:G2', 'University of Cebu', header_format)
            worksheet.merge_range('A3:G3', 'Sit-In Monitoring System Report', subheader_format)
            worksheet.merge_range('A4:G4', f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', date_format)
            
            # Add some space
            worksheet.set_row(4, 10)  # Set row 5 height to 10 as spacing
            
            # Write column headers and data with formatting
            table_header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#003366',  # Dark blue
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })
            
            data_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            alt_row_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bg_color': '#F2F2F2'  # Light gray
            })
            
            # Write the column headers
            for col_num, column in enumerate(df.columns):
                worksheet.write(5, col_num, column, table_header_format)
            
            # Write the data rows with alternating colors
            for row_num, row_data in enumerate(df.values):
                row_format = alt_row_format if row_num % 2 else data_format
                for col_num, value in enumerate(row_data):
                    worksheet.write(row_num + 6, col_num, value, row_format)
            
            # Auto-adjust columns' width
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
        
        # Add title and header
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        header_style = styles["Heading2"]
        subheader_style = styles["Heading3"]
        normal_style = styles["Normal"]
        
        # Enhance title style
        title_style.alignment = 1  # Center alignment
        title_style.fontSize = 18
        header_style.alignment = 1
        subheader_style.alignment = 1
        
        # Create title and headers
        title = Paragraph("College of Computer Studies", title_style)
        subtitle = Paragraph("University of Cebu", header_style)
        report_name = Paragraph("Sit-In Monitoring System Report", subheader_style)
        date_line = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style)
        date_line.alignment = 1  # Center align date as well
        
        # Add to elements
        elements.append(title)
        elements.append(Spacer(1, 6))  # Small space after title
        elements.append(subtitle)
        elements.append(Spacer(1, 6))  # Small space after subtitle
        elements.append(report_name)
        elements.append(Spacer(1, 10))  # Larger space after report name
        elements.append(date_line)
        elements.append(Spacer(1, 20))  # Add some space before table
        
        # Convert DataFrame to a list of lists for the table
        data_list = [df.columns.tolist()] + df.values.tolist()
        
        # Create the table
        table = Table(data_list)
        
        # Style the table
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
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
            
        # Calculate total sessions before adding points
        sessions_before = initial_points // 3
        
        # Add points to the user's record
        session_record.lab_usage_points += points
        
        # Calculate total sessions after adding points
        sessions_after = session_record.lab_usage_points // 3
        
        # Calculate how many new sessions to add
        sessions_to_add = sessions_after - sessions_before
        
        if sessions_to_add > 0:
            # Add the converted sessions
            session_record.remaining_sessions += sessions_to_add
            
        db.session.commit()
        
        # Calculate the changes for reporting
        points_added = points
        sessions_change = session_record.remaining_sessions - initial_sessions
        
        # Create a detailed message
        message = f"Added {points} points to student {student_id}."
        if sessions_change > 0:
            message += f" Converted points into {sessions_change} new sit-in sessions."
        
        # For form submissions that expect a redirect, handle that differently
        if request.headers.get('Accept') == 'text/html':
            flash(message, "success")
            return redirect(url_for("admin_dashboard"))
        
        return jsonify({
            "success": True, 
            "message": message,
            "points_added": points_added,
            "sessions_added": sessions_change,
            "remaining_points": session_record.lab_usage_points,
            "remaining_sessions": session_record.remaining_sessions
        })
        
    except Exception as e:
        print(f"Error in add_points: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

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

@app.route("/get_lab_pc_status")
def get_lab_pc_status():
    try:
        # Print request details for debugging
        print(f"get_lab_pc_status request received. Args: {request.args}")
        print(f"Request method: {request.method}")
        print(f"Request headers: {request.headers}")
        
        # Temporarily bypass authentication for testing
        # if "user_id" not in session or session.get("role") != "admin":
        #     print("Unauthorized access attempt to get_lab_pc_status")
        #     return jsonify({"error": "Unauthorized access"}), 403
            
        lab_id = request.args.get("lab_id")
        print(f"Lab ID from request: {lab_id}")
        
        if not lab_id:
            print("No lab_id provided")
            return jsonify([])
            
        try:
            lab_id = int(lab_id)
            print(f"Parsed lab_id as integer: {lab_id}")
        except ValueError:
            print(f"Invalid lab_id format: {lab_id}")
            return jsonify({"error": "Invalid lab ID format"}), 400
        
        # Check if Labs table exists in the database
        inspector = db.inspect(db.engine)
        if "Labs" not in inspector.get_table_names():
            print("Labs table doesn't exist! Creating it now...")
            db.Model.metadata.tables["Labs"].create(db.engine)
            
            # Add default labs
            labs = ["524", "544", "523", "526", "Mac lab"]
            for lab_name in labs:
                new_lab = Lab(lab_name=lab_name)
                db.session.add(new_lab)
                print(f"Added lab: {lab_name}")
            
            db.session.commit()
            print("Labs created successfully")
        
        # Check if PCs table exists in the database
        if "PCs" not in inspector.get_table_names():
            print("PCs table doesn't exist! Creating it now...")
            db.Model.metadata.tables["PCs"].create(db.engine)
            
            # Add default PCs
            labs_from_db = Lab.query.all()
            for lab in labs_from_db:
                for i in range(1, 51):
                    pc_name = f"PC-{i}"
                    new_pc = PC(lab_id=lab.id, pc_name=pc_name, is_available=True)
                    db.session.add(new_pc)
                    
            db.session.commit()
            print("PCs created successfully")
        
        # Get the lab to verify it exists
        lab = Lab.query.get(lab_id)
        if not lab:
            print(f"Lab not found for ID: {lab_id}, creating default lab")
            
            # Create a default lab based on ID (1-5 maps to the standard labs)
            lab_names = {1: "524", 2: "544", 3: "523", 4: "526", 5: "Mac lab"}
            default_lab_name = lab_names.get(lab_id, f"Lab {lab_id}")
            
            lab = Lab(id=lab_id, lab_name=default_lab_name)
            db.session.add(lab)
            db.session.commit()
            print(f"Created default lab: {default_lab_name} with ID {lab_id}")
        
        print(f"Found/Created lab: {lab.lab_name} (ID: {lab.id})")
        
        # Get all PCs for the specified lab
        pcs = PC.query.filter_by(lab_id=lab_id).all()
        print(f"Found {len(pcs)} PCs for lab: {lab.lab_name}")
        
        if not pcs:
            print(f"No PCs found for lab: {lab.lab_name}, creating default PCs")
            # If no PCs found, create default PCs for this lab (50 PCs)
            for i in range(1, 51):
                pc_name = f"PC-{i}"
                new_pc = PC(lab_id=lab_id, pc_name=pc_name, is_available=True)
                db.session.add(new_pc)
            
            try:
                db.session.commit()
                print(f"Created 50 default PCs for lab: {lab.lab_name}")
                # Re-query to get the newly created PCs
                pcs = PC.query.filter_by(lab_id=lab_id).all()
                print(f"Successfully retrieved {len(pcs)} newly created PCs")
            except Exception as e:
                db.session.rollback()
                print(f"Failed to create PCs in database: {str(e)}")
                
                # Generate PC data without saving to database as fallback
                pcs = []
                for i in range(1, 51):
                    pc = type('', (), {})()  # Create a simple object
                    pc.id = i
                    pc.pc_name = f"PC-{i}"
                    pc.is_available = True
                    pcs.append(pc)
                print(f"Generated {len(pcs)} temporary PC objects")
        
        # Check for any incorrect PC status in database
        # This fixes the PC-12 issue by verifying active reservations
        # For any PC that's marked as unavailable, check if there is an actual
        # active reservation for it
        for pc in pcs:
            if not pc.is_available:
                # Check if there's an active reservation for this PC
                reservation = Reservation.query.filter_by(
                    lab=lab.lab_name,
                    available_pc=pc.pc_name
                ).filter(Reservation.status.in_(["Pending", "Approved", "Sit-in"])).first()
                
                # If no active reservation found but PC is marked as unavailable,
                # fix the status
                if not reservation:
                    print(f"Fixed status for {pc.pc_name} in lab {lab.lab_name}: " +
                          f"No active reservation but PC was marked as unavailable")
                    pc.is_available = True
                    db.session.commit()
        
        pc_data = []
        for pc in pcs:
            pc_info = {
                "id": pc.id,
                "pc_name": pc.pc_name,
                "is_available": pc.is_available,
                "reservation": None
            }
            
            # If PC is not available, find reservation information
            if not pc.is_available:
                reservation = Reservation.query.filter_by(
                    lab=lab.lab_name,
                    available_pc=pc.pc_name
                ).filter(Reservation.status.in_(["Pending", "Approved", "Sit-in"])).first()
                
                if reservation:
                    pc_info["reservation"] = {
                        "id": reservation.id,
                        "student_id": reservation.student_id,
                        "firstname": reservation.firstname,
                        "lastname": reservation.lastname,
                        "purpose": reservation.purpose,
                        "date": reservation.date,
                        "time": reservation.time,
                        "status": reservation.status
                    }
                else:
                    # If we reach here, there's no reservation but PC is marked as unavailable
                    # This is a logical error, so we'll fix it here as well
                    pc.is_available = True
                    db.session.commit()
                    pc_info["is_available"] = True
                    print(f"Fixed status discrepancy for {pc.pc_name} during response generation")
            
            pc_data.append(pc_info)
        
        print(f"Returning data for {len(pc_data)} PCs")
        return jsonify(pc_data)
    except Exception as e:
        print(f"Unexpected error in get_lab_pc_status: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/get_labs")
def get_labs():
    labs = Lab.query.all()
    lab_data = []
    for lab in labs:
        pc_count = PC.query.filter_by(lab_id=lab.id).count()
        lab_data.append({"id": lab.id, "name": lab.lab_name, "pc_count": pc_count})
    return jsonify(lab_data)

@app.route("/lab_schedules")
def lab_schedules():
    """
    Display the lab schedules to students using a direct approach.
    Shows all labs and their schedules in a tabular format.
    """
    try:
        # Get current time for display in the template
        current_time = datetime.now()
        
        # Handle JSON request for AJAX loading
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
            return get_lab_schedules_json()
        
        # Initial page load without data - the schedules will be loaded via AJAX
        return render_template(
            "lab_schedules.html", 
            lab_schedules={},
            now=current_time,
            ajax_loading=True
        )
    except Exception as e:
        print(f"Error in lab_schedules route: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template(
            "lab_schedules.html", 
            lab_schedules={}, 
            error_message=f"Failed to load lab schedules: {str(e)}", 
            now=datetime.now()
        )

@app.route("/api/lab_schedules")
def get_lab_schedules_json():
    """
    API endpoint to get lab schedules in JSON format.
    Used by the AJAX request from the student view.
    """
    try:
        # Use demo data if requested through URL parameter
        if request.args.get('demo', 'false').lower() == 'true':
            print("Using demo data for lab schedules API")
            demo_data = create_demo_schedules()
            lab_schedules_data = {}
            
            # Get all labs to ensure we include empty labs too
            labs = Lab.query.all()
            
            # Map each lab name to its demo data
            lab_mapping = {
                "524": "Lab 524",
                "544": "Lab 544",
                "523": "Lab 523",
                "526": "Lab 526",
                "Mac lab": "Mac lab"
            }
            
            for lab in labs:
                demo_key = lab_mapping.get(lab.lab_name, "Lab 524")
                lab_schedules_data[lab.lab_name] = demo_data.get(demo_key, [])
        else:
            # Clear the cache to ensure fresh data
            cache_key = f"lab_schedules_{datetime.now().strftime('%Y%m%d_%H')}"
            cache.delete(cache_key)
            
            # Fetch actual schedules from the database directly
            lab_schedules_data = {}
            
            # Get all labs
            labs = Lab.query.all()
            
            # Log labs found for debugging
            print(f"Found {len(labs)} labs in database: {[lab.lab_name for lab in labs]}")
            
            # Initialize an empty list for each lab, ensuring all labs are included
            for lab in labs:
                lab_schedules_data[lab.lab_name] = []
            
            # Query all lab schedules
            schedules = LabSchedule.query.all()
            print(f"Found {len(schedules)} schedules in database")
            
            # Group schedules by lab
            for schedule in schedules:
                # Get lab name from the lab_id
                lab = Lab.query.get(schedule.lab_id)
                if lab:
                    # Convert database schedule to dict format for template
                    schedule_dict = {
                        "id": schedule.id,
                        "title": schedule.title,
                        "description": schedule.description or "",
                        "day_of_week": schedule.day_of_week,
                        "start_time": schedule.start_time,
                        "end_time": schedule.end_time,
                        "max_capacity": schedule.max_capacity or "",
                        "course": schedule.course or ""
                    }
                    
                    # Add to the appropriate lab's schedule list
                    if lab.lab_name in lab_schedules_data:
                        lab_schedules_data[lab.lab_name].append(schedule_dict)
                    else:
                        # If lab name is not in dictionary yet, add it
                        lab_schedules_data[lab.lab_name] = [schedule_dict]
        
                    print(f"Added schedule for {lab.lab_name}: {schedule.day_of_week} {schedule.start_time}-{schedule.end_time}")
            
            # Force-ensure all labs are included, even if empty
            labs_to_include = ["523", "524", "526", "544", "Mac lab"]
            for lab_name in labs_to_include:
                if lab_name not in lab_schedules_data:
                    lab_schedules_data[lab_name] = []
            
            # Store in cache for 5 minutes only (reduced from 1 hour)
            cache.set(cache_key, lab_schedules_data, timeout=300)
        
        # Return JSON response
        return jsonify({
            "success": True,
            "lab_schedules": lab_schedules_data,
            "cached": False,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in get_lab_schedules_json: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# Add this at the beginning of the file with other imports
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})

@app.route("/admin/upload_lab_schedules", methods=["POST"])
def upload_lab_schedules():
    """Handle bulk upload of lab schedules via CSV or Excel file"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized access"}), 403
    
    try:
        if 'schedule_file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['schedule_file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        # Check file extension
        allowed_extensions = {'csv', 'xlsx', 'xls'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({"success": False, "error": "Invalid file type. Please upload a CSV or Excel file."}), 400
        
        # Process file based on type
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Validate required columns
        required_columns = ['lab_name', 'title', 'day_of_week', 'start_time', 'end_time']
        for col in required_columns:
            if col not in df.columns:
                return jsonify({"success": False, "error": f"Missing required column: {col}"}), 400
        
        # Process each row and add to database
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Find lab by name
                lab_name = row['lab_name']
                lab = Lab.query.filter_by(lab_name=lab_name).first()
                
                if not lab:
                    errors.append(f"Row {index+2}: Lab '{lab_name}' not found")
                    error_count += 1
                    continue
                
                # Process days (handle multi-day formats)
                day_format = row['day_of_week']
                days_to_add = []
                
                if day_format == "MWF":
                    days_to_add = ["Monday", "Wednesday", "Friday"]
                elif day_format == "TTH":
                    days_to_add = ["Tuesday", "Thursday"]
                elif day_format == "FS":
                    days_to_add = ["Friday", "Saturday"]
                else:
                    # Single day
                    days_to_add = [day_format]
                
                # Add a schedule entry for each day
                for day in days_to_add:
                    new_schedule = LabSchedule(
                        lab_id=lab.id,
                        title=row['title'],
                        description=row.get('description', ''),
                        day_of_week=day,
                        start_time=row['start_time'],
                        end_time=row['end_time'],
                        max_capacity=str(row.get('max_capacity', '')),
                        course=str(row.get('course', ''))
                    )
                    db.session.add(new_schedule)
                    success_count += 1
            
            except Exception as e:
                errors.append(f"Row {index+2}: {str(e)}")
                error_count += 1
        
        if success_count > 0:
            db.session.commit()
            
            # Clear cache to ensure updated schedules are shown
            cache_keys = [k for k in cache.cache._cache.keys() if k.startswith('lab_schedules_')]
            for key in cache_keys:
                cache.delete(key)
        
        return jsonify({
            "success": True,
            "message": f"Successfully added {success_count} schedules with {error_count} errors",
            "errors": errors
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Error uploading lab schedules: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

def create_demo_schedules():
    """Create demo schedules for testing purposes"""
    return {
        'Lab 524': [
            {
                "id": 1,
                "title": "Class in Session",
                "description": "Data Structures and Algorithms",
                "day_of_week": "Monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "max_capacity": "30",
                "course": "CCS 229"
            },
            {
                "id": 2,
                "title": "Available",
                "description": "Open Lab",
                "day_of_week": "Monday",
                "start_time": "13:00",
                "end_time": "15:00",
                "max_capacity": "30",
                "course": ""
            },
            {
                "id": 3,
                "title": "Reserved",
                "description": "Web Development Workshop",
                "day_of_week": "Wednesday",
                "start_time": "10:00",
                "end_time": "12:00",
                "max_capacity": "25",
                "course": "CCS 235"
            }
        ],
        'Lab 544': [
            {
                "id": 4,
                "title": "Class in Session",
                "description": "Database Systems",
                "day_of_week": "Tuesday",
                "start_time": "07:30",
                "end_time": "10:30",
                "max_capacity": "40",
                "course": "CCS 240"
            },
            {
                "id": 5,
                "title": "Available",
                "description": "Open Lab Time",
                "day_of_week": "Thursday",
                "start_time": "09:00",
                "end_time": "12:00",
                "max_capacity": "40",
                "course": ""
            }
        ],
        'Lab 523': [
            {
                "id": 6,
                "title": "Class in Session",
                "description": "Web Programming",
                "day_of_week": "Monday",
                "start_time": "10:00",
                "end_time": "12:00",
                "max_capacity": "35",
                "course": "CCS 235"
            },
            {
                "id": 7,
                "title": "Reserved",
                "description": "PSITS Meeting",
                "day_of_week": "Friday",
                "start_time": "14:00",
                "end_time": "16:00",
                "max_capacity": "35",
                "course": ""
            }
        ],
        'Lab 526': [
            {
                "id": 8,
                "title": "Class in Session",
                "description": "Introductory Programming",
                "day_of_week": "Tuesday",
                "start_time": "07:30",
                "end_time": "10:30",
                "max_capacity": "40",
                "course": "CCS 101"
            },
            {
                "id": 9,
                "title": "Reserved",
                "description": "Programming Competition Training",
                "day_of_week": "Wednesday",
                "start_time": "15:00",
                "end_time": "18:00",
                "max_capacity": "25",
                "course": ""
            }
        ],
        'Mac lab': [
            {
                "id": 10,
                "title": "Available",
                "description": "Mac Lab Open Hours",
                "day_of_week": "Friday",
                "start_time": "13:00",
                "end_time": "17:00",
                "max_capacity": "20",
                "course": ""
            },
            {
                "id": 11,
                "title": "Class in Session",
                "description": "iOS App Development",
                "day_of_week": "Monday",
                "start_time": "13:00",
                "end_time": "16:00",
                "max_capacity": "20",
                "course": "CCS 255"
            }
        ]
    }

@app.route("/admin/lab_schedules")
def admin_lab_schedules():
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for("home"))
    
    labs = Lab.query.all()
    schedules = LabSchedule.query.order_by(LabSchedule.lab_id, LabSchedule.day_of_week, LabSchedule.start_time).all()
    
    return render_template("admin_lab_schedules.html", user=get_current_user(), labs=labs, schedules=schedules)

@app.route("/admin_resources")
def admin_resources():
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to access this page", "danger")
        return redirect(url_for("home"))
    
    # Get all resources from database
    resources = Resource.query.order_by(Resource.upload_date.desc()).all()
    
    return render_template("resources.html", user=get_current_user(), resources=resources)

@app.route("/student_resources")
def student_resources():
    # Check if user is logged in
    if "user_id" not in session:
        flash("You must be logged in to access resources", "danger")
        return redirect(url_for("home"))
    
    # Get only enabled resources from database
    resources = Resource.query.filter_by(status="enabled").order_by(Resource.upload_date.desc()).all()
    
    return render_template("student_resources.html", user=get_current_user(), resources=resources)

@app.route("/upload_resource", methods=["POST"])
def upload_resource():
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to upload resources", "danger")
        return redirect(url_for("home"))
    
    try:
        title = request.form.get("title")
        description = request.form.get("description", "")
        file = request.files.get("resourceFile")
        original_filename = request.form.get("original_filename")
        
        if not title or not file:
            flash("Title and file are required", "warning")
            return redirect(url_for("admin_resources"))
        
        # Check if file exists and has allowed extension
        if file and file.filename:
            # Get file extension
            file_ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
            
            # If original_filename is not set, use the file's filename
            if not original_filename:
                original_filename = file.filename
            
            # Generate a unique filename to prevent collisions
            unique_filename = str(uuid.uuid4()) + "." + file_ext
            
            # Create resources dir if it doesn't exist
            resources_dir = os.path.join(app.config["UPLOAD_FOLDER"], "resources")
            if not os.path.exists(resources_dir):
                os.makedirs(resources_dir)
            
            # Save file to resources directory
            file_path = os.path.join(resources_dir, unique_filename)
            file.save(file_path)
            
            # Create resource record in database
            new_resource = Resource(
                title=title,
                description=description,
                file_path=os.path.join("resources", unique_filename),
                file_type=file_ext,
                uploaded_by=session["user_id"],
                original_filename=original_filename,
                status="enabled"
            )
            
            db.session.add(new_resource)
            db.session.commit()
            
            flash("Resource uploaded successfully", "success")
        else:
            flash("No file selected", "warning")
    
    except Exception as e:
        db.session.rollback()
        flash(f"Error uploading resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/download_resource/<int:resource_id>")
def download_resource(resource_id):
    # Check if user is logged in
    if "user_id" not in session:
        flash("You must be logged in to download resources", "danger")
        return redirect(url_for("home"))
    
    # Get resource from database
    resource = Resource.query.get_or_404(resource_id)
    
    # If resource is disabled and user is not admin, prevent download
    if resource.status == "disabled" and session.get("role") != "admin":
        flash("This resource is currently disabled", "warning")
        return redirect(url_for("student_resources"))
    
    try:
        # Construct file path
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], resource.file_path)
        
        # Check if file exists
        if not os.path.exists(file_path):
            flash("Resource file not found", "danger")
            return redirect(url_for("student_resources"))
        
        # Use original filename for download if available, otherwise use the title
        if resource.original_filename:
            download_name = resource.original_filename
        else:
            download_name = f"{resource.title}.{resource.file_type}"
        
        # Send file as attachment
        return send_file(
            file_path, 
            as_attachment=True, 
            download_name=download_name,
            mimetype=f"application/{resource.file_type}"
        )
    
    except Exception as e:
        flash(f"Error downloading resource: {str(e)}", "danger")
        return redirect(url_for("student_resources"))

@app.route("/admin/delete_resource/<int:resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    # Get resource from database
    resource = Resource.query.get_or_404(resource_id)
    
    try:
        # Delete file from filesystem
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], resource.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete resource record from database
        db.session.delete(resource)
        db.session.commit()
        
        return jsonify({"success": True, "message": "Resource deleted successfully"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error deleting resource: {str(e)}"}), 500

@app.route("/admin/add_lab_schedule", methods=["POST"])
def add_lab_schedule():
    """Add a new lab schedule from the admin interface"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized access"}), 403
    
    try:
        lab_id = request.form.get("lab_id")
        
        # Get the lab name for debugging
        lab = Lab.query.get(lab_id)
        if lab:
            print(f"Adding schedule for lab: {lab.lab_name} (ID: {lab.id})")
        else:
            print(f"Lab with ID {lab_id} not found")
            return jsonify({"success": False, "error": "Selected lab does not exist"}), 400
            
        title = request.form.get("title")
        description = request.form.get("description", "")
        day_format = request.form.get("day_of_week")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        
        # Note: In the UI, "max_capacity" is used to store max capacity
        max_capacity = request.form.get("max_capacity", "")
        course = request.form.get("course", "")
        
        # Print form data for debugging
        print(f"Form data: lab_id={lab_id}, title={title}, day_format={day_format}, " 
              f"start_time={start_time}, end_time={end_time}, max_capacity={max_capacity}, course={course}")
        
        # Validate required fields
        if not all([lab_id, title, day_format, start_time, end_time]):
            missing_fields = []
            if not lab_id: missing_fields.append("Lab")
            if not title: missing_fields.append("Status")
            if not day_format: missing_fields.append("Day Schedule")
            if not start_time: missing_fields.append("Start Time")
            if not end_time: missing_fields.append("End Time") 
            return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
        
        # Validate time format
        try:
            # Attempt to parse times to ensure they're valid
            start_hour, start_minute = map(int, start_time.split(':'))
            end_hour, end_minute = map(int, end_time.split(':'))
            
            # Validate time values
            if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59):
                return jsonify({"success": False, "error": "Invalid start time format"}), 400
            if not (0 <= end_hour <= 23 and 0 <= end_minute <= 59):
                return jsonify({"success": False, "error": "Invalid end time format"}), 400
                
            # Check that end time is after start time
            if end_hour < start_hour or (end_hour == start_hour and end_minute <= start_minute):
                return jsonify({"success": False, "error": "End time must be after start time"}), 400
        except (ValueError, AttributeError):
            return jsonify({"success": False, "error": "Invalid time format. Use HH:MM format."}), 400
        
        # Convert day format to individual days for student view compatibility
        days_to_add = []
        if day_format == "MWF":
            days_to_add = ["Monday", "Wednesday", "Friday"]
        elif day_format == "TTH":
            days_to_add = ["Tuesday", "Thursday"]
        elif day_format == "FS":
            days_to_add = ["Friday", "Saturday"]
        else:
            # Single day or custom format
            days_to_add = [day_format]
        
        # Add a schedule entry for each day
        added_schedules = []
        for day in days_to_add:
            new_schedule = LabSchedule(
                lab_id=lab_id,
                title=title,
                description=description,
                day_of_week=day,  # Use individual day name
                start_time=start_time,
                end_time=end_time,
                max_capacity=max_capacity,  # Using max_capacity field for max capacity
                course=course
            )
            db.session.add(new_schedule)
            added_schedules.append(new_schedule)
        
        # Commit all schedule additions at once
        db.session.commit()
        
        # Print the added schedules for debugging
        print(f"Added {len(added_schedules)} schedules for lab {lab.lab_name}:")
        for schedule in added_schedules:
            print(f"  - Day: {schedule.day_of_week}, Time: {schedule.start_time}-{schedule.end_time}, "
                  f"Max Capacity: {schedule.max_capacity}, ID: {schedule.id}")
        
        # Clear any cached schedules
        db.session.expire_all()
        
        return jsonify({
            "success": True, 
            "message": f"Added {len(added_schedules)} schedule(s) successfully", 
            "schedules": [{"id": s.id, "day": s.day_of_week} for s in added_schedules]
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error adding lab schedule: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/edit_lab_schedule/<int:schedule_id>", methods=["POST"])
def edit_lab_schedule(schedule_id):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized access"}), 403
    
    try:
        schedule = LabSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        # Get the original day and lab before update
        original_day = schedule.day_of_week
        original_lab_id = schedule.lab_id
        
        # Get lab info for debugging
        original_lab = Lab.query.get(original_lab_id)
        original_lab_name = original_lab.lab_name if original_lab else "Unknown"
        
        # Update fields
        lab_id = request.form.get("lab_id", schedule.lab_id)
        new_lab = Lab.query.get(lab_id)
        new_lab_name = new_lab.lab_name if new_lab else "Unknown"
        
        title = request.form.get("title", schedule.title)
        description = request.form.get("description", schedule.description)
        day_format = request.form.get("day_of_week", schedule.day_of_week)
        start_time = request.form.get("start_time", schedule.start_time)
        end_time = request.form.get("end_time", schedule.end_time)
        max_capacity = request.form.get("max_capacity", schedule.max_capacity)  # Max capacity stored in max_capacity field
        course = request.form.get("course", schedule.course)
        
        print(f"Editing schedule: {schedule_id}")
        print(f"  Original lab: {original_lab_name} (ID: {original_lab_id}), Day: {original_day}")
        print(f"  New lab: {new_lab_name} (ID: {lab_id}), Day format: {day_format}")
        
        # Check if day format is a multi-day format
        is_multi_day_format = day_format in ["MWF", "TTH", "FS"]
        
        # If changing to a multi-day format, create additional entries
        if is_multi_day_format:
            # Map day formats to individual days
            day_mapping = {
                "MWF": ["Monday", "Wednesday", "Friday"],
                "TTH": ["Tuesday", "Thursday"],
                "FS": ["Friday", "Saturday"]
            }
            
            # Update the current schedule for the first day
            schedule.lab_id = lab_id
            schedule.title = title
            schedule.description = description
            schedule.day_of_week = day_mapping[day_format][0]  # First day
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.max_capacity = max_capacity
            schedule.course = course
            
            # Create additional schedules for other days
            added_schedules = []
            for day in day_mapping[day_format][1:]:  # Skip first day
                new_schedule = LabSchedule(
                    lab_id=lab_id,
                    title=title,
                    description=description,
                    day_of_week=day,
                    start_time=start_time,
                    end_time=end_time,
                    max_capacity=max_capacity,
                    course=course
                )
                db.session.add(new_schedule)
                added_schedules.append(new_schedule)
                
            print(f"  Created {len(added_schedules)} additional schedules for other days in {day_format}")
        else:
            # Regular update for single day
            schedule.lab_id = lab_id
            schedule.title = title
            schedule.description = description
            schedule.day_of_week = day_format
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.max_capacity = max_capacity
            schedule.course = course
            
            print(f"  Updated single day schedule to {day_format}")
        
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"Error editing lab schedule: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/delete_lab_schedule/<int:schedule_id>", methods=["DELETE"])
def delete_lab_schedule(schedule_id):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized access"}), 403
    
    try:
        schedule = LabSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
        
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# Start the background thread for scheduled tasks
if __name__ == "__main__":
    # Create a daemon thread to run the scheduled task
    scheduler_thread = threading.Thread(target=archive_sit_in_records, daemon=True)
    scheduler_thread.start()
    
    app.run(debug=True, host="0.0.0.0",  port="5000")

@app.route("/admin/create_test_schedule", methods=["GET"])
def admin_create_test_schedule():
    """Create a test schedule entry - for debugging purposes only"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to access this page.", "danger")
        return redirect(url_for("login"))
    
    try:
        # Get all labs
        labs = Lab.query.all()
        
        if len(labs) == 0:
            # Create default labs if none exist
            default_labs = [
                Lab(lab_name="Lab 524"),
                Lab(lab_name="Lab 526"),
                Lab(lab_name="Lab 523"),
                Lab(lab_name="Lab 544"),
                Lab(lab_name="Mac lab")
            ]
            db.session.add_all(default_labs)
            db.session.commit()
            labs = Lab.query.all()
        
        # Create a test schedule entry
        test_lab = labs[0]  # Use the first lab
        
        # Check if a test schedule already exists
        existing_test = LabSchedule.query.filter_by(
            lab_id=test_lab.id,
            day_of_week="Monday",
            title="Class in Session"
        ).first()
        
        if existing_test:
            flash(f"Test schedule already exists for {test_lab.lab_name}.", "info")
        else:
            # Create a test schedule
            test_schedule = LabSchedule(
                lab_id=test_lab.id,
                title="Class in Session",
                description="Test Schedule - Created Automatically",
                day_of_week="Monday",
                start_time="08:00",
                end_time="10:00",
                max_capacity="30",  # Max capacity
                course="CCS TEST"
            )
            
            db.session.add(test_schedule)
            db.session.commit()
            
            flash(f"Test schedule created for {test_lab.lab_name}.", "success")
        
        # Get all schedules for debugging
        all_schedules = LabSchedule.query.all()
        schedule_info = [
            f"ID: {s.id}, Lab: {Lab.query.get(s.lab_id).lab_name if Lab.query.get(s.lab_id) else 'Unknown'}, "
            f"Day: {s.day_of_week}, Time: {s.start_time}-{s.end_time}, Title: {s.title}"
            for s in all_schedules
        ]
        
        return render_template(
            "admin_test_schedule.html", 
            labs=labs,
            schedules=all_schedules,
            schedule_info=schedule_info
        )
    
    except Exception as e:
        flash(f"Error creating test schedule: {str(e)}", "danger")
        return redirect(url_for("admin_lab_schedules"))

@app.route("/insert_test_schedules")
def insert_test_schedules():
    """Insert test schedules for all labs to help with debugging."""
    try:
        labs = Lab.query.all()
        if not labs:
            # Create default labs if needed
            default_labs = [
                Lab(lab_name="Lab 524"),
                Lab(lab_name="Lab 526"),
                Lab(lab_name="Lab 523"),
                Lab(lab_name="Lab 544"),
                Lab(lab_name="Mac lab")
            ]
            db.session.add_all(default_labs)
            db.session.commit()
            labs = Lab.query.all()
            
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        statuses = ["Available", "Reserved", "Class in Session", "Maintenance", "Available"]
        
        schedules_added = 0
        
        # Create schedules for each lab
        for lab in labs:
            for i, (day, status) in enumerate(zip(days, statuses)):
                # Skip if a schedule already exists for this lab and day
                existing = LabSchedule.query.filter_by(lab_id=lab.id, day_of_week=day).first()
                if existing:
                    continue
                
                # Create a test schedule with different times each day
                hour = 8 + i  # Different hour for each day (8:00, 9:00, etc.)
                new_schedule = LabSchedule(
                    lab_id=lab.id,
                    title=status,
                    description=f"Test schedule for {lab.lab_name} on {day}",
                    day_of_week=day,
                    start_time=f"{hour:02d}:00",
                    end_time=f"{hour+2:02d}:00",
                    max_capacity=str(20 + i*5),  # Max capacity (20, 25, 30, 35, 40)
                    course=f"TEST{i+101}" if status == "Class in Session" else ""
                )
                db.session.add(new_schedule)
                schedules_added += 1
        
        db.session.commit()
        
        message = f"Successfully added {schedules_added} test schedules"
        return f"""
        <html>
            <body style="font-family: Arial; padding: 20px; max-width: 800px; margin: 0 auto;">
                <h1>Test Schedules Added</h1>
                <p>{message}</p>
                <p><a href="/lab_schedules">View Lab Schedules</a></p>
                <p><a href="/admin/lab_schedules">Go to Admin Schedules Page</a></p>
            </body>
        </html>
        """
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"""
        <html>
            <body style="font-family: Arial; padding: 20px; max-width: 800px; margin: 0 auto;">
                <h1>Error Adding Test Schedules</h1>
                <p>Error: {str(e)}</p>
                <pre>{error_details}</pre>
                <p><a href="/lab_schedules">View Lab Schedules</a></p>
            </body>
        </html>
        """

@app.route("/direct_lab_schedules")
def direct_lab_schedules():
    """
    A simplified and direct approach to showing lab schedules
    This bypasses most template logic and directly injects HTML
    """
    try:
        # Create direct access to demo data
        demo_data = create_demo_schedules()
        current_time = datetime.now()
        
        # Get labs from the database 
        labs = Lab.query.all()
        
        # Create direct mapping from lab names to demo data
        lab_mapping = {
            "524": "Lab 524",
            "544": "Lab 544",
            "523": "Lab 523",
            "526": "Lab 526",
            "Mac lab": "Mac lab"
        }
        
        # Initialize direct HTML sections
        regular_labs_html = ""
        mac_lab_html = ""
        
        # Generate HTML for each lab
        for lab in labs:
            demo_key = lab_mapping.get(lab.lab_name, "Lab 524")
            schedules = demo_data.get(demo_key, [])
            
            # Skip the Mac lab - handle it separately
            if lab.lab_name == "Mac lab":
                continue
                
            # Start the lab section
            section_html = f"""
            <div class="lab-section">
                <h3 class="lab-title">{lab.lab_name}</h3>
            """
            
            if schedules:
                # Start the table
                section_html += """
                <table class="schedules-table">
                    <thead>
                        <tr>
                            <th>Day</th>
                            <th>Time</th>
                            <th>Status</th>
                            <th>Max Capacity</th>
                            <th>Course</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                # Group schedules by day
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                schedules_by_day = {}
                
                for day in days:
                    day_schedules = [s for s in schedules if s["day_of_week"] == day]
                    if day_schedules:
                        schedules_by_day[day] = sorted(day_schedules, key=lambda x: x["start_time"])
                
                # Add days and their schedules
                for day, day_schedules in schedules_by_day.items():
                    # Day header
                    section_html += f"""
                    <tr class="day-label">
                        <td colspan="5">{day}</td>
                    </tr>
                    """
                    
                    # Add schedules for this day
                    for schedule in day_schedules:
                        # Determine status class
                        status_class = ""
                        if schedule["title"] == "Available":
                            status_class = "status-available"
                        elif schedule["title"] == "Reserved":
                            status_class = "status-reserved"
                        elif schedule["title"] == "Maintenance":
                            status_class = "status-maintenance"
                        elif "Class" in schedule["title"]:
                            status_class = "status-class"
                            
                        # Add the schedule row
                        section_html += f"""
                        <tr>
                            <td></td>
                            <td>{schedule["start_time"]} - {schedule["end_time"]}</td>
                            <td>
                                <span class="{status_class}">{schedule["title"]}</span>
                                {"<br><small>" + schedule["description"] + "</small>" if schedule["description"] else ""}
                            </td>
                            <td>{schedule["max_capacity"]}</td>
                            <td>{schedule["course"]}</td>
                        </tr>
                        """
                
                # End the table
                section_html += """
                    </tbody>
                </table>
                """
            else:
                # No schedules for this lab
                section_html += """
                <div class="no-schedules">
                    No schedules available for this lab.
                </div>
                """
            
            # End the lab section
            section_html += """
            </div>
            """
            
            regular_labs_html += section_html
        
        # Handle Mac lab separately
        if "Mac lab" in [lab.lab_name for lab in labs]:
            mac_schedules = demo_data.get("Mac lab", [])
            
            # Start Mac lab section
            mac_lab_html = """
            <div class="mac-lab-container">
                <div class="lab-section">
                    <h3 class="lab-title">Mac Lab</h3>
            """
            
            if mac_schedules:
                # Start table
                mac_lab_html += """
                <table class="schedules-table">
                    <thead>
                        <tr>
                            <th>Day</th>
                            <th>Time</th>
                            <th>Status</th>
                            <th>Max Capacity</th>
                            <th>Course</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                # Group schedules by day
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                mac_schedules_by_day = {}
                
                for day in days:
                    day_schedules = [s for s in mac_schedules if s["day_of_week"] == day]
                    if day_schedules:
                        mac_schedules_by_day[day] = sorted(day_schedules, key=lambda x: x["start_time"])
                
                # Add days and schedules
                for day, day_schedules in mac_schedules_by_day.items():
                    # Day header
                    mac_lab_html += f"""
                    <tr class="day-label">
                        <td colspan="5">{day}</td>
                    </tr>
                    """
                    
                    # Add schedules
                    for schedule in day_schedules:
                        # Determine status class
                        status_class = ""
                        if schedule["title"] == "Available":
                            status_class = "status-available"
                        elif schedule["title"] == "Reserved":
                            status_class = "status-reserved"
                        elif schedule["title"] == "Maintenance":
                            status_class = "status-maintenance"
                        elif "Class" in schedule["title"]:
                            status_class = "status-class"
                            
                        # Add schedule row
                        mac_lab_html += f"""
                        <tr>
                            <td></td>
                            <td>{schedule["start_time"]} - {schedule["end_time"]}</td>
                            <td>
                                <span class="{status_class}">{schedule["title"]}</span>
                                {"<br><small>" + schedule["description"] + "</small>" if schedule["description"] else ""}
                            </td>
                            <td>{schedule["max_capacity"]}</td>
                            <td>{schedule["course"]}</td>
                        </tr>
                        """
                
                # End table
                mac_lab_html += """
                    </tbody>
                </table>
                """
            else:
                # No schedules
                mac_lab_html += """
                <div class="no-schedules">
                    No schedules available for this lab.
                </div>
                """
            
            # End Mac lab section
            mac_lab_html += """
                </div>
            </div>
            """
        
        # Render a simple template that includes our HTML sections
        return render_template(
            "lab_schedules_direct.html", 
            regular_labs_html=regular_labs_html,
            mac_lab_html=mac_lab_html,
            now=current_time
        )
    except Exception as e:
        print(f"Error in direct_lab_schedules route: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error loading schedules: {str(e)}"

@app.route("/admin/toggle_resource_status/<int:resource_id>", methods=["POST"])
def toggle_resource_status(resource_id):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    # Add debug print statements
    print(f"Attempting to toggle status for resource ID: {resource_id}")
    
    # Get resource from database
    resource = Resource.query.get_or_404(resource_id)
    print(f"Resource found: {resource.title}")
    
    try:
        # Get status from request
        data = request.get_json()
        print(f"Request data: {data}")
        new_status = data.get("status", "enabled")
        print(f"New status: {new_status}")
        
        # Check if the resource object has a status attribute
        print(f"Resource has status attribute: {hasattr(resource, 'status')}")
        if hasattr(resource, 'status'):
            print(f"Current status: {resource.status}")
        
        # Check if the status column exists
        if not hasattr(resource, "status"):
            # If we need to update the database schema
            from sqlalchemy import text
            try:
                # Add status column if it doesn't exist
                print("Adding status column to Resources table")
                db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
                db.session.commit()
                print("Added status column to Resources table")
            except Exception as schema_error:
                print(f"Error adding status column: {str(schema_error)}")
                db.session.rollback()
                return jsonify({
                    "success": False, 
                    "message": "Database schema issue. Status column not found.",
                    "error": str(schema_error)
                }), 500
        
        # Try setting the status using SQLAlchemy directly
        try:
            print(f"Setting status to {new_status} for resource {resource_id}")
            
            # Try direct database update
            from sqlalchemy import text
            db.session.execute(
                text("UPDATE Resources SET status = :status WHERE id = :id"),
                {"status": new_status, "id": resource_id}
            )
            db.session.commit()
            print("Status updated successfully via direct SQL")
            
            return jsonify({
                "success": True, 
                "message": f"Resource {new_status} successfully", 
                "new_status": new_status
            }), 200
        except Exception as direct_update_error:
            print(f"Direct update error: {str(direct_update_error)}")
            db.session.rollback()
            
            # Try the ORM approach as fallback
            try:
                resource.status = new_status
                db.session.commit()
                print("Status updated successfully via ORM")
                return jsonify({
                    "success": True, 
                    "message": f"Resource {new_status} successfully", 
                    "new_status": new_status
                }), 200
            except Exception as orm_error:
                print(f"ORM update error: {str(orm_error)}")
                db.session.rollback()
                return jsonify({
                    "success": False, 
                    "message": f"Error updating resource status with ORM: {str(orm_error)}",
                    "error_type": str(type(orm_error))
                }), 500
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({
            "success": False, 
            "message": f"Error updating resource status: {str(e)}",
            "error_type": str(type(e))
        }), 500

@app.route("/debug/resources")
def debug_resources():
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
        
    resources = Resource.query.all()
    results = []
    
    for r in resources:
        results.append({
            "id": r.id,
            "title": r.title,
            "status": r.status if hasattr(r, "status") else "no_status_attr",
            "original_filename": r.original_filename if hasattr(r, "original_filename") else "no_filename_attr",
            "file_type": r.file_type
        })
    
    # Also check database schema
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = inspector.get_columns("Resources")
    column_names = [c["name"] for c in columns]
    
    return jsonify({
        "resources": results,
        "columns": column_names,
        "resource_count": len(results)
    })

def ensure_resource_table_schema():
    """Ensure the Resources table has all necessary columns."""
    try:
        with app.app_context():
            from sqlalchemy import text, inspect
            
            print("Checking Resources table schema...")
            
            # Get current columns
            inspector = inspect(db.engine)
            if "Resources" not in inspector.get_table_names():
                print("Resources table doesn't exist yet. It will be created with the correct schema.")
                return
                
            columns = inspector.get_columns("Resources")
            column_names = [c["name"] for c in columns]
            print(f"Current columns in Resources table: {column_names}")
            
            # Check for status column
            if "status" not in column_names:
                print("Status column not found in Resources table. Adding it now.")
                db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
                db.session.commit()
                print("Successfully added status column")
            else:
                print("Status column exists in Resources table")
            
            # Check for original_filename column
            if "original_filename" not in column_names:
                print("Original_filename column not found in Resources table. Adding it now.")
                db.session.execute(text("ALTER TABLE Resources ADD COLUMN original_filename VARCHAR(255)"))
                db.session.commit()
                print("Successfully added original_filename column")
            else:
                print("Original_filename column exists in Resources table")
            
            # Verify column operation by testing a direct update on the first resource
            resources = Resource.query.all()
            if resources:
                first_resource = resources[0]
                resource_id = first_resource.id
                print(f"Testing status column operation on resource ID {resource_id}")
                
                # Try to get the current status
                try:
                    # Check if the attribute exists in the model
                    if hasattr(first_resource, 'status'):
                        current_status = first_resource.status
                        print(f"Current status via ORM: {current_status}")
                    else:
                        print("Status attribute not in ORM model")
                        
                    # Try direct SQL query
                    result = db.session.execute(text("SELECT status FROM Resources WHERE id = :id"), {"id": resource_id}).fetchone()
                    if result:
                        print(f"Current status via SQL: {result[0]}")
                    else:
                        print("Could not retrieve status via SQL")
                except Exception as e:
                    print(f"Error reading status: {str(e)}")
                
                # Try updating the status column
                try:
                    print("Testing status column update...")
                    current_value = db.session.execute(
                        text("SELECT status FROM Resources WHERE id = :id"), 
                        {"id": resource_id}
                    ).fetchone()
                    
                    if current_value:
                        current_status = current_value[0]
                        new_status = "disabled" if current_status == "enabled" else "enabled"
                        
                        # Update using direct SQL
                        db.session.execute(
                            text("UPDATE Resources SET status = :status WHERE id = :id"), 
                            {"status": new_status, "id": resource_id}
                        )
                        db.session.commit()
                        
                        # Verify the update
                        updated_value = db.session.execute(
                            text("SELECT status FROM Resources WHERE id = :id"), 
                            {"id": resource_id}
                        ).fetchone()
                        
                        if updated_value and updated_value[0] == new_status:
                            print(f"Status column is working properly. Updated from {current_status} to {updated_value[0]}")
                        else:
                            print(f"Status update verification failed. Expected {new_status}, got {updated_value[0] if updated_value else 'None'}")
                            
                        # Reset to original value
                        db.session.execute(
                            text("UPDATE Resources SET status = :status WHERE id = :id"), 
                            {"status": current_status, "id": resource_id}
                        )
                        db.session.commit()
                        print(f"Reset status back to {current_status}")
                    else:
                        print("Could not retrieve current status value")
                except Exception as test_error:
                    print(f"Error testing status column: {str(test_error)}")
                    db.session.rollback()
            
            print("Resource table schema verification completed")
    except Exception as e:
        print(f"Error updating Resources table schema: {str(e)}")
        import traceback
        traceback.print_exc()

# Run the schema update at app start
ensure_resource_table_schema()

@app.route("/admin/reset_resources_table", methods=["GET"])
def reset_resources_table():
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        from sqlalchemy import text, inspect
        
        inspector = inspect(db.engine)
        
        # Check if Resources table exists
        if "Resources" in inspector.get_table_names():
            # Get current resources to back them up
            resources_data = []
            resources = Resource.query.all()
            
            for resource in resources:
                resource_dict = {
                    "id": resource.id,
                    "title": resource.title,
                    "description": resource.description,
                    "file_path": resource.file_path,
                    "file_type": resource.file_type,
                    "upload_date": resource.upload_date,
                    "uploaded_by": resource.uploaded_by
                }
                
                # Try to get original_filename and status if they exist
                if hasattr(resource, 'original_filename'):
                    resource_dict['original_filename'] = resource.original_filename
                
                if hasattr(resource, 'status'):
                    resource_dict['status'] = resource.status
                
                resources_data.append(resource_dict)
            
            # Drop the table
            db.session.execute(text("DROP TABLE IF EXISTS Resources"))
            db.session.commit()
            
            # Recreate the table
            db.Model.metadata.tables["Resources"].create(db.engine)
            db.session.commit()
            
            # Restore the data
            for resource_dict in resources_data:
                new_resource = Resource(
                    title=resource_dict["title"],
                    description=resource_dict["description"],
                    file_path=resource_dict["file_path"],
                    file_type=resource_dict["file_type"],
                    upload_date=resource_dict["upload_date"],
                    uploaded_by=resource_dict["uploaded_by"],
                    status=resource_dict.get("status", "enabled"),
                    original_filename=resource_dict.get("original_filename", None)
                )
                db.session.add(new_resource)
            
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Resources table reset successfully",
                "resources_restored": len(resources_data)
            })
        else:
            # Just create the table
            db.Model.metadata.tables["Resources"].create(db.engine)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Resources table created successfully",
                "resources_restored": 0
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        
        return jsonify({
            "success": False,
            "message": f"Error resetting Resources table: {str(e)}",
            "error_type": str(type(e))
        }), 500

@app.route("/routes")
def list_routes():
    result = []
    for rule in app.url_map.iter_rules():
        result.append({
            "endpoint": rule.endpoint,
            "methods": [m for m in rule.methods if m != "HEAD" and m != "OPTIONS"],
            "route": str(rule)
        })
    return jsonify(result)

@app.route("/admin/resources/toggle/<int:resource_id>", methods=["GET", "POST"])
def toggle_resource_status_new(resource_id):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to toggle resource status", "danger")
        return redirect(url_for("admin_dashboard"))
    
    # Add debug print statements
    print(f"NEW ROUTE: Attempting to toggle status for resource ID: {resource_id}")
    
    # Get resource from database
    resource = Resource.query.get_or_404(resource_id)
    print(f"Resource found: {resource.title}")
    
    try:
        # Get status from request
        if request.method == "POST":
            data = request.get_json()
            print(f"POST Request data: {data}")
            new_status = data.get("status", "enabled")
        else:
            # For GET requests, check query parameters
            new_status = request.args.get("status")
            print(f"GET parameter status: {new_status}")
            
            # If no status provided or invalid, toggle the current status
            if new_status not in ["enabled", "disabled"]:
                current_status = getattr(resource, "status", "enabled").lower()
                new_status = "disabled" if current_status == "enabled" else "enabled"
            
        print(f"New status: {new_status}")
        
        # Try direct database update
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE Resources SET status = :status WHERE id = :id"),
            {"status": new_status, "id": resource_id}
        )
        db.session.commit()
        print("Status updated successfully via direct SQL")
        
        if request.method == "GET":
            flash(f"Resource '{resource.title}' {new_status} successfully", "success")
            return redirect(url_for("admin_resources"))
        else:
            return jsonify({
                "success": True, 
                "message": f"Resource {new_status} successfully", 
                "new_status": new_status
            }), 200
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        
        if request.method == "GET":
            flash(f"Error updating resource status: {str(e)}", "danger")
            return redirect(url_for("admin_resources"))
        else:
            return jsonify({
                "success": False, 
                "message": f"Error updating resource status: {str(e)}",
                "error_type": str(type(e))
            }), 500

@app.route("/admin/resource/set_status/<int:resource_id>/<string:status>", methods=["GET", "POST"])
def set_resource_status_direct(resource_id, status):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    print(f"DIRECT ROUTE: Setting resource {resource_id} status to {status}")
    
    try:
        # Get resource to verify it exists
        resource = Resource.query.get_or_404(resource_id)
        
        # Direct SQL update - should work regardless of ORM configuration
        from sqlalchemy import text
        sql = "UPDATE Resources SET status = :status WHERE id = :id"
        db.session.execute(text(sql), {"status": status, "id": resource_id})
        db.session.commit()
        
        flash(f"Resource {resource.title} {status} successfully", "success")
        return redirect(url_for("admin_resources"))
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash(f"Error updating resource status: {str(e)}", "danger")
        return redirect(url_for("admin_resources"))

@app.before_first_request
def check_resource_status_column():
    try:
        # Directly check if the status column actually exists in the database
        with app.app_context():
            from sqlalchemy import text, inspect
            
            inspector = inspect(db.engine)
            if "Resources" not in inspector.get_table_names():
                print("Resources table doesn't exist yet")
                return
            
            # Try a direct query to check if the status column can be accessed
            try:
                # Use a test query that should fail if the column doesn't exist
                result = db.session.execute(text("SELECT id, status FROM Resources LIMIT 1")).fetchone()
                print(f"Status column verified: {result}")
            except Exception as sql_error:
                print(f"Status column verification failed: {str(sql_error)}")
                print("Attempting to add the status column...")
                
                try:
                    # Add the column if it doesn't exist
                    db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
                    db.session.commit()
                    print("Successfully added status column")
                except Exception as add_error:
                    print(f"Error adding status column: {str(add_error)}")
            
            # Verify schema one more time
            columns = inspector.get_columns("Resources")
            column_names = [c["name"] for c in columns]
            print(f"Verified columns in Resources table: {column_names}")
    except Exception as e:
        print(f"Error checking resource status column: {str(e)}")
        import traceback
        traceback.print_exc()

@app.route("/admin/direct_toggle/<int:resource_id>/<string:new_status>", methods=["POST"])
def direct_toggle_resource(resource_id, new_status):
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
    
    print(f"Direct toggle route called for resource ID {resource_id}, new status: {new_status}")
    
    try:
        # Validate the status parameter
        if new_status not in ['enabled', 'disabled']:
            flash("Invalid status value", "danger")
            return redirect(url_for("admin_resources"))
            
        # Get resource to verify it exists
        resource = Resource.query.get_or_404(resource_id)
        
        # Use raw SQL to ensure it works regardless of SQLAlchemy model
        from sqlalchemy import text
        db.session.execute(
            text("UPDATE Resources SET status = :status WHERE id = :id"),
            {"status": new_status, "id": resource_id}
        )
        db.session.commit()
        
        flash(f"Resource '{resource.title}' has been {new_status}", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error in direct_toggle_resource: {str(e)}")
        flash(f"Error updating resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

################################################
# Register resource routes Blueprint
################################################
try:
    from resource_routes import resource_bp
    app.register_blueprint(resource_bp, url_prefix='/resource')
    print("Resource routes blueprint registered")
except ImportError as e:
    print(f"Could not import resource_routes module: {e}")

# Direct routes - guaranteed to work
@app.route("/direct/disable/<int:resource_id>")
def direct_disable(resource_id):
    """Directly disable a resource"""
    try:
        with app.app_context():
            # Use a simple SQL UPDATE statement
            db.session.execute(db.text(f"UPDATE Resources SET status = 'disabled' WHERE id = {resource_id}"))
            db.session.commit()
            flash("Resource disabled successfully", "success")
    except Exception as e:
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect("/admin_resources")

@app.route("/direct/enable/<int:resource_id>")
def direct_enable(resource_id):
    """Directly enable a resource"""
    try:
        with app.app_context():
            # Use a simple SQL UPDATE statement
            db.session.execute(db.text(f"UPDATE Resources SET status = 'enabled' WHERE id = {resource_id}"))
            db.session.commit()
            flash("Resource enabled successfully", "success")
    except Exception as e:
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect("/admin_resources")

@app.before_first_request
def ensure_resource_model_has_status():
    """Ensure that the Resource model and database table have all necessary columns"""
    print("Checking Resource model and database columns...")
    
    # Check model attributes
    resource_has_status = hasattr(Resource, 'status')
    resource_has_original_filename = hasattr(Resource, 'original_filename')
    
    print(f"Resource model has status attribute: {resource_has_status}")
    print(f"Resource model has original_filename attribute: {resource_has_original_filename}")
    
    # If model doesn't have these attributes, add them
    if not resource_has_status:
        print("Adding status attribute to Resource model")
        Resource.status = db.Column(db.String(20), nullable=False, default="enabled")
    
    if not resource_has_original_filename:
        print("Adding original_filename attribute to Resource model")
        Resource.original_filename = db.Column(db.String(255), nullable=True)
    
    # Create the table if it doesn't exist
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    
    if "Resources" not in inspector.get_table_names():
        print("Creating Resources table")
        db.create_all()
    
    # Check if the database table has the status column
    try:
        # Direct query to check if columns exist
        from sqlalchemy import text
        result = db.session.execute(text("SELECT status FROM Resources LIMIT 1")).fetchone()
        print("Status column exists in database table")
    except Exception as e:
        print(f"Error checking status column: {e}")
        try:
            print("Attempting to add status column to database table")
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
            db.session.commit()
            print("Successfully added status column to database")
        except Exception as alter_error:
            print(f"Error adding status column: {alter_error}")
    
    # Check if the database table has the original_filename column
    try:
        result = db.session.execute(text("SELECT original_filename FROM Resources LIMIT 1")).fetchone()
        print("Original_filename column exists in database table")
    except Exception as e:
        print(f"Error checking original_filename column: {e}")
        try:
            print("Attempting to add original_filename column to database table")
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN original_filename VARCHAR(255)"))
            db.session.commit()
            print("Successfully added original_filename column to database")
        except Exception as alter_error:
            print(f"Error adding original_filename column: {alter_error}")

@app.route("/admin/resources/disable/<int:resource_id>", methods=["GET", "POST"])
def admin_resources_disable_route(resource_id):
    """Route that matches the URL in the template"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
        
    try:
        # Get resource
        resource = Resource.query.get_or_404(resource_id)
        
        # Update resource status
        resource.status = "disabled"
        db.session.commit()
        
        flash(f"Resource '{resource.title}' disabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/admin/resources/enable/<int:resource_id>", methods=["GET", "POST"])
def admin_resources_enable_route(resource_id):
    """Route that matches the URL in the template"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
        
    try:
        # Get resource
        resource = Resource.query.get_or_404(resource_id)
        
        # Update resource status
        resource.status = "enabled"
        db.session.commit()
        
        flash(f"Resource '{resource.title}' enabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/admin_resources/disable/<int:resource_id>", methods=["GET", "POST"])
def admin_resources_disable_direct(resource_id):
    """Disable a resource"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
        
    try:
        # Get resource
        resource = Resource.query.get_or_404(resource_id)
        
        # Update resource status
        resource.status = "disabled"
        db.session.commit()
        
        flash(f"Resource '{resource.title}' disabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/admin_resources/enable/<int:resource_id>", methods=["GET", "POST"])
def admin_resources_enable_direct(resource_id):
    """Enable a resource"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
        
    try:
        # Get resource
        resource = Resource.query.get_or_404(resource_id)
        
        # Update resource status
        resource.status = "enabled"
        db.session.commit()
        
        flash(f"Resource '{resource.title}' enabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/direct_enable/<int:resource_id>")
def direct_enable_resource(resource_id):
    """Direct enable using simple SQL"""
    try:
        # Simple SQL update
        db.session.execute(db.text(f"UPDATE Resources SET status = 'enabled' WHERE id = {resource_id}"))
        db.session.commit()
        flash("Resource enabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/direct_disable/<int:resource_id>")
def direct_disable_resource(resource_id):
    """Direct disable using simple SQL"""
    try:
        # Simple SQL update
        db.session.execute(db.text(f"UPDATE Resources SET status = 'disabled' WHERE id = {resource_id}"))
        db.session.commit()
        flash("Resource disabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@app.route("/toggle_resource_status/<int:resource_id>")
def toggle_resource_status_simple(resource_id):
    """Simple GET route to toggle a resource's status without AJAX"""
    # Redirect to direct enable or disable routes based on current status
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to modify resources", "danger")
        return redirect(url_for("home"))
    
    try:
        # Get current status
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT status FROM Resources WHERE id = :id"),
            {"id": resource_id}
        ).fetchone()
        
        if not result:
            flash("Resource not found", "danger")
            return redirect(url_for("admin_resources"))
        
        current_status = result.status if result.status else 'enabled'
        current_status = current_status.lower()
        
        # Redirect to the appropriate route
        if current_status == 'enabled':
            return redirect(f"/direct_disable/{resource_id}")
        else:
            return redirect(f"/direct_enable/{resource_id}")
            
    except Exception as e:
        flash(f"Error determining resource status: {str(e)}", "danger")
        return redirect(url_for("admin_resources"))
    
# Ensure resource model and database have all required columns
@app.before_first_request
def ensure_resource_model_and_db():
    """Comprehensive function to ensure the Resource model and database are correctly set up"""
    print("Ensuring Resource model and database are properly configured...")
    
    try:
        # Check if Resources table exists
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        if "Resources" not in inspector.get_table_names():
            print("Resources table doesn't exist yet - creating it")
            db.create_all()
            print("Resources table created successfully")
            return
            
        # Get existing columns
        columns = inspector.get_columns("Resources")
        column_names = [c["name"] for c in columns]
        print(f"Existing columns in Resources table: {column_names}")
        
        # Check and add status column if missing
        if "status" not in column_names:
            print("Adding status column to Resources table")
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
            db.session.commit()
            print("Status column added successfully")
            
            # Update existing records
            db.session.execute(text("UPDATE Resources SET status = 'enabled'"))
            db.session.commit()
            print("All existing resources set to 'enabled' status")
        
        # Check and add original_filename column if missing
        if "original_filename" not in column_names:
            print("Adding original_filename column to Resources table")
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN original_filename VARCHAR(255)"))
            db.session.commit()
            print("Original_filename column added successfully")
            
        # Validate that the model can access these columns
        resource = Resource.query.first()
        if resource:
            print(f"Testing column access on resource ID {resource.id}")
            try:
                status = resource.status
                print(f"Status column accessible: {status}")
            except Exception as e:
                print(f"Error accessing status column via ORM: {e}")
                
            try:
                filename = resource.original_filename
                print(f"Original_filename column accessible: {filename}")
            except Exception as e:
                print(f"Error accessing original_filename column via ORM: {e}")
        else:
            print("No resources found to test column access")
            
        print("Resource model and database setup completed successfully")
            
    except Exception as e:
        print(f"Error ensuring resource model and database: {e}")
        import traceback
        traceback.print_exc()

@app.route("/admin/fix_resources_table")
def admin_fix_resources_table():
    """Fix the resources table if it's broken"""
    # Check if user is admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to perform this action", "danger")
        return redirect(url_for("home"))
    
    try:
        # Use SQLite-specific PRAGMA to check table info
        from sqlalchemy import text
        
        # Check if table exists
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='Resources'")).fetchone()
        if not result:
            # Create the table
            db.create_all()
            flash("Resources table created successfully", "success")
            return redirect(url_for("admin_resources"))
        
        # Get table columns
        columns = db.session.execute(text("PRAGMA table_info(Resources)")).fetchall()
        column_names = [col[1] for col in columns]
        
        changes_made = False
        
        # Check for status column
        if "status" not in column_names:
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN status VARCHAR(20) DEFAULT 'enabled' NOT NULL"))
            db.session.commit()
            db.session.execute(text("UPDATE Resources SET status = 'enabled'"))
            db.session.commit()
            changes_made = True
            flash("Added missing 'status' column to Resources table", "success")
        
        # Check for original_filename column
        if "original_filename" not in column_names:
            db.session.execute(text("ALTER TABLE Resources ADD COLUMN original_filename VARCHAR(255)"))
            db.session.commit()
            changes_made = True
            flash("Added missing 'original_filename' column to Resources table", "success")
        
        # Verify we can access resources
        try:
            resources = Resource.query.all()
            count = len(resources)
            
            # Try toggling a resource status as a test
            if resources:
                test_resource = resources[0]
                old_status = test_resource.status if hasattr(test_resource, 'status') else 'enabled'
                new_status = 'disabled' if old_status == 'enabled' else 'enabled'
                
                # Toggle test
                db.session.execute(
                    text("UPDATE Resources SET status = :status WHERE id = :id"),
                    {"status": new_status, "id": test_resource.id}
                )
                db.session.commit()
                
                # Toggle back
                db.session.execute(
                    text("UPDATE Resources SET status = :status WHERE id = :id"),
                    {"status": old_status, "id": test_resource.id}
                )
                db.session.commit()
                
                flash(f"Verified toggle functionality works for {count} resources", "success")
            else:
                flash("No resources found, but table structure is valid", "info")
        
        except Exception as access_error:
            flash(f"Error accessing resources: {str(access_error)}", "warning")
            return redirect(url_for("admin_resources"))
        
        if not changes_made:
            flash("Resources table is already properly configured", "info")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error fixing resources table: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
