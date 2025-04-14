from app import app, db
from sqlalchemy import text

def add_lab_usage_points_column():
    try:
        with app.app_context():
            # Check if the column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('Sessions')]
            
            if 'lab_usage_points' not in columns:
                # Add the column if it doesn't exist
                db.session.execute(text("ALTER TABLE Sessions ADD lab_usage_points INT NOT NULL DEFAULT 0"))
                db.session.commit()
                print("Successfully added 'lab_usage_points' column to Sessions table.")
            else:
                print("Column 'lab_usage_points' already exists in Sessions table.")
                
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()

if __name__ == "__main__":
    add_lab_usage_points_column() 