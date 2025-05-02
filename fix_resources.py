import sqlite3
import os
import sys

# Set the path to the SQLite database file
DATABASE_PATH = "sit_in_monitoring.db"

def fix_resources_table():
    """Add the status column to the Resources table if it doesn't exist"""
    
    print("Starting resources table fix script...")
    
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database file not found at {DATABASE_PATH}")
        print("Please specify the correct path to your database file.")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # List all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables in the database: {[table[0] for table in tables]}")
        
        # Check if the Resources table exists (case-insensitive)
        found_resources_table = False
        table_name = None
        for table in tables:
            if table[0].lower() == 'resources':
                found_resources_table = True
                table_name = table[0]
                break
        
        if not found_resources_table:
            print("Resources table does not exist in the database")
            return False
        
        print(f"Found Resources table as: {table_name}")
        
        # Get the columns in the Resources table
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Current columns in Resources table: {column_names}")
        
        # Check if status column exists
        if 'status' not in column_names:
            print("Adding status column to Resources table...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN status TEXT DEFAULT 'enabled' NOT NULL")
            conn.commit()
            print("Status column added successfully")
            
            # Update existing records to have status='enabled'
            cursor.execute(f"UPDATE {table_name} SET status = 'enabled'")
            conn.commit()
            print("All existing resources set to 'enabled' status")
        else:
            print("Status column already exists")
        
        # Check if original_filename column exists
        if 'original_filename' not in column_names:
            print("Adding original_filename column to Resources table...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN original_filename TEXT")
            conn.commit()
            print("Original_filename column added successfully")
        else:
            print("Original_filename column already exists")
        
        # Verify the changes
        cursor.execute(f"PRAGMA table_info({table_name})")
        updated_columns = cursor.fetchall()
        updated_column_names = [col[1] for col in updated_columns]
        print(f"Updated columns in Resources table: {updated_column_names}")
        
        # Query a few rows to show sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        print(f"Sample resources data: {rows}")
        
        print("Resources table fix completed successfully")
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    result = fix_resources_table()
    sys.exit(0 if result else 1) 