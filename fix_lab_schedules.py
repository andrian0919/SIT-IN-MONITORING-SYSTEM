"""
Fix Lab Schedules - Diagnostic and Repair Tool
This script checks the database for lab schedules and ensures they're properly configured.
It also creates test schedules if none exist.
"""

import os
from datetime import datetime
from app import app, db, Lab, LabSchedule

def main():
    with app.app_context():
        print("\n===== LAB SCHEDULES DIAGNOSTIC =====")
        
        # Check if database file exists
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'database.db')
        print(f"Checking database at: {db_path}")
        print(f"Database exists: {os.path.exists(db_path)}")
        
        # Check if labs table exists and has entries
        labs = Lab.query.all()
        print(f"\nFound {len(labs)} labs:")
        
        if len(labs) == 0:
            print("No labs found. Creating default labs...")
            default_labs = [
                Lab(lab_name="524"),
                Lab(lab_name="526"),
                Lab(lab_name="523"),
                Lab(lab_name="544"),
                Lab(lab_name="Mac lab")
            ]
            db.session.add_all(default_labs)
            db.session.commit()
            print("Default labs created.")
            labs = Lab.query.all()
            
        # Print lab details
        for lab in labs:
            print(f"  - ID: {lab.id}, Name: {lab.lab_name}")
        
        # Check if lab schedule entries exist
        schedules = LabSchedule.query.all()
        print(f"\nFound {len(schedules)} schedule entries:")
        
        # Print first 5 schedules for debugging
        for i, schedule in enumerate(schedules[:5]):
            lab = Lab.query.get(schedule.lab_id)
            lab_name = lab.lab_name if lab else "Unknown Lab"
            print(f"  - Schedule {i+1}: Lab: {lab_name}, Day: {schedule.day_of_week}, "
                  f"Time: {schedule.start_time}-{schedule.end_time}, Status: {schedule.title}")
        
        # FORCE CREATE SCHEDULES FOR EACH LAB
        print("\nForce creating test schedules for all labs...")
        
        # Delete existing schedules if requested
        if input("Delete all existing schedules? (y/n): ").lower() == 'y':
            try:
                LabSchedule.query.delete()
                db.session.commit()
                print("All existing schedules deleted.")
                schedules = []
            except Exception as e:
                print(f"Error deleting schedules: {e}")
        
        # Create test schedules for each day of the week to ensure the system works
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
            test_schedules = LabSchedule.query.all()
            print(f"Verified total of {len(test_schedules)} schedules now in database.")
        else:
            print("No new schedules were created.")
            
        print("\n===== DIAGNOSTICS COMPLETE =====")
        print("\nIf lab schedules are still not appearing on the student view, please check:")
        print("1. Make sure you're accessing the correct URL: /lab_schedules")
        print("2. Check the Python console for any error messages")
        print("3. Try using the debug view by adding ?debug=true to the URL: /lab_schedules?debug=true")
        print("4. Verify the database connection is working correctly")
        print("\nYou can go to http://localhost:5000/lab_schedules to see if the schedules appear now.")

if __name__ == "__main__":
    main() 