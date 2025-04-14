import os
import pandas as pd
from sqlalchemy import func
from database import db

def generate_purpose_report(app):
    if not os.path.exists("reports"):
        os.makedirs("reports")
        
    filename = os.path.join("reports", "purpose_report.xlsx")
    
    with app.app_context():
        # Query to get purpose statistics
        purpose_stats = (
            db.session.query(
                'purpose',
                func.count('id').label('count')
            )
            .select_from(db.Model.metadata.tables['Reservation'])
            .group_by('purpose')
            .all()
        )
    
        # Convert to DataFrame
        df = pd.DataFrame([
            {'Purpose': stat[0], 'Count': stat[1]}
            for stat in purpose_stats
        ])
        
        # Save to Excel
        df.to_excel(filename, index=False)
    
    return filename

def generate_year_level_report(app):
    if not os.path.exists("reports"):
        os.makedirs("reports")
        
    filename = os.path.join("reports", "year_level_report.xlsx")
    
    with app.app_context():
        # Query to get year level statistics
        year_level_stats = (
            db.session.query(
                'Users.yearlevel',
                func.count('Reservation.id').label('count')
            )
            .select_from(db.Model.metadata.tables['Reservation'])
            .join(db.Model.metadata.tables['Users'], 
                  db.Model.metadata.tables['Users'].c.student_id == 
                  db.Model.metadata.tables['Reservation'].c.student_id)
            .group_by('Users.yearlevel')
            .all()
        )
    
        # Convert to DataFrame
        df = pd.DataFrame([
            {'Year Level': stat[0], 'Count': stat[1]}
            for stat in year_level_stats
        ])
        
        # Save to Excel
        df.to_excel(filename, index=False)
    
    return filename