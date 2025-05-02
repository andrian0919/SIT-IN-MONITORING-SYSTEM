"""
Add Lab Schedules - Direct Script
This script adds test schedules for all labs without prompting.
"""

from app import app, db, Lab, LabSchedule

def add_schedules():
    with app.app_context():
        print("Adding schedules to all labs...")
        
        # Get all labs
        labs = Lab.query.all()
        if not labs:
            print("No labs found. Please run fix_lab_schedules.py first.")
            return
        
        print(f"Found {len(labs)} labs:")
        for lab in labs:
            print(f"  - ID: {lab.id}, Name: {lab.lab_name}")
        
        # Create test schedules for each day of the week
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        statuses = ["Available", "Reserved", "Class in Session", "Maintenance", "Available"]
        
        schedules_created = 0
        
        for lab in labs:
            print(f"Creating schedules for lab: {lab.lab_name}")
            for i, (day, status) in enumerate(zip(days, statuses)):
                # Create a test schedule with different times each day
                hour = 8 + i  # Different hour for each day (8:00, 9:00, etc.)
                
                # Check if this lab already has a schedule for this day and time
                existing = LabSchedule.query.filter_by(
                    lab_id=lab.id,
                    day_of_week=day,
                    start_time=f"{hour:02d}:00"
                ).first()
                
                if existing:
                    print(f"  - Schedule for {day} at {hour:02d}:00 already exists, skipping.")
                    continue
                
                new_schedule = LabSchedule(
                    lab_id=lab.id,
                    title=status,
                    description=f"Test schedule for {day}",
                    day_of_week=day,
                    start_time=f"{hour:02d}:00",
                    end_time=f"{hour+2:02d}:00",
                    max_capacity="30",
                    course="TEST101" if status == "Class in Session" else ""
                )
                db.session.add(new_schedule)
                schedules_created += 1
                print(f"  - Created {status} schedule for {day} ({hour:02d}:00-{hour+2:02d}:00)")
        
        if schedules_created > 0:
            db.session.commit()
            print(f"Successfully created {schedules_created} new test schedules.")
            
            # Verify the test schedules were created
            all_schedules = LabSchedule.query.all()
            print(f"Verified total of {len(all_schedules)} schedules now in database.")
        else:
            print("No new schedules were created.")
        
        print("\nDone! You can now check the lab schedules at http://localhost:5000/lab_schedules")

if __name__ == "__main__":
    add_schedules() 