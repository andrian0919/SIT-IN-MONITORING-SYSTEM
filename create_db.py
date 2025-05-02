"""
Database Initialization Script
This script creates the database and its tables if they don't exist.
"""

from app import app, db, Lab, LabSchedule, User
from datetime import datetime

def initialize_database():
    """Initialize the database and create tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created.")
        
        # Create default labs if none exist
        labs = Lab.query.all()
        if not labs:
            print("Creating default labs...")
            default_labs = [
                Lab(lab_name="Lab 524"),
                Lab(lab_name="Lab 526"),
                Lab(lab_name="Lab 523"),
                Lab(lab_name="Lab 544"),
                Lab(lab_name="Mac lab")
            ]
            db.session.add_all(default_labs)
            db.session.commit()
            print("Default labs created.")
            
        # Create a default admin user if none exists
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            print("Creating default admin user...")
            admin_user = User(
                student_id="admin123",
                password="pbkdf2:sha256:150000$XoLK9npF$c33c54c8c67d7b0e31fa684651f7142f0383bbeb889912a359ea48f7c71286c7",  # password: 'admin123'
                email="admin@example.com",
                lastname="Admin",
                firstname="System",
                role="admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created.")
            
        # Check if there are any lab schedules
        schedules = LabSchedule.query.all()
        if not schedules:
            print("Creating sample lab schedules...")
            labs = Lab.query.all()
            if labs:
                first_lab = labs[0]
                
                # Create a sample schedule for Monday
                monday_schedule = LabSchedule(
                    lab_id=first_lab.id,
                    title="Available",
                    description="Open Lab Hours",
                    day_of_week="Monday",
                    start_time="09:00",
                    end_time="12:00",
                    max_capacity="30",  # Max capacity
                    course=""
                )
                
                # Create a sample schedule for Wednesday
                wednesday_schedule = LabSchedule(
                    lab_id=first_lab.id,
                    title="Class in Session",
                    description="Programming Class",
                    day_of_week="Wednesday",
                    start_time="13:00",
                    end_time="16:00",
                    max_capacity="25",  # Max capacity
                    course="CS101"
                )
                
                db.session.add(monday_schedule)
                db.session.add(wednesday_schedule)
                db.session.commit()
                print("Sample lab schedules created.")
        
        print("Database initialization complete.")

if __name__ == "__main__":
    initialize_database()
    print("\nDatabase is now ready to use.")
    print("You can start the application by running `python app.py`")
    print("Then visit http://localhost:5000/lab_schedules to view lab schedules.") 