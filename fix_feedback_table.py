from app import app, db
from sqlalchemy import text

with app.app_context():
    # Try to add the lab column if it doesn't exist
    try:
        db.session.execute(text("ALTER TABLE Feedback ADD lab NVARCHAR(50) NULL"))
        db.session.commit()
        print("Successfully added 'lab' column to Feedback table")
    except Exception as e:
        db.session.rollback()
        print(f"Error adding column: {str(e)}")
        
        # If column already exists, let's just update NULL values
        try:
            # Update any NULL lab values to 'Unknown'
            db.session.execute(text("UPDATE Feedback SET lab = 'Unknown' WHERE lab IS NULL"))
            db.session.commit()
            print("Updated NULL lab values to 'Unknown'")
        except Exception as e2:
            db.session.rollback()
            print(f"Error updating NULL values: {str(e2)}") 