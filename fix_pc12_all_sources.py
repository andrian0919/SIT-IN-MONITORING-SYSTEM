import sqlite3
import os
import sys
import traceback
import json
import subprocess
import time

def reset_database_tables():
    """Reset the PC-12 status in all database tables"""
    print("=== Resetting database tables ===")
    
    try:
        # Connect to the database
        conn = sqlite3.connect('sit_in_monitoring.db')
        cursor = conn.cursor()
        
        # 1. First check if tables exist, if not create them
        print("Checking for required tables...")
        
        # Labs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Labs'")
        if not cursor.fetchone():
            print("Creating Labs table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Labs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lab_name TEXT NOT NULL
                )
            """)
            
            # Add labs
            labs = ["524", "544", "523", "526", "Mac lab"]
            for lab_name in labs:
                cursor.execute("INSERT INTO Labs (lab_name) VALUES (?)", (lab_name,))
                print(f"Added lab: {lab_name}")
            
            print("Labs table created successfully")
        
        # PCs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='PCs'")
        if not cursor.fetchone():
            print("Creating PCs table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS PCs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lab_id INTEGER NOT NULL,
                    pc_name TEXT NOT NULL,
                    is_available BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (lab_id) REFERENCES Labs(id)
                )
            """)
            
            # Add PCs for each lab
            cursor.execute("SELECT id, lab_name FROM Labs")
            labs = cursor.fetchall()
            
            for lab_id, lab_name in labs:
                # Add 50 PCs for each lab
                for i in range(1, 51):
                    pc_name = f"PC-{i}"
                    cursor.execute(
                        "INSERT INTO PCs (lab_id, pc_name, is_available) VALUES (?, ?, 1)",
                        (lab_id, pc_name)
                    )
                
                print(f"Added 50 PCs for lab {lab_name}")
            
            print("PCs table created successfully")
        
        # Reservation table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Reservation'")
        if not cursor.fetchone():
            print("Creating Reservation table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Reservation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    lastname TEXT,
                    firstname TEXT,
                    date TEXT,
                    time TEXT,
                    purpose TEXT,
                    lab TEXT,
                    available_pc TEXT,
                    status TEXT DEFAULT 'Pending',
                    time_in TEXT,
                    time_out TEXT
                )
            """)
            print("Reservation table created successfully")
        
        # 2. Now update PC-12 status for labs 523 and 524
        print("\nUpdating PC-12 status for labs 523 and 524...")
        
        # Force update PCs table for PC-12 in both labs
        cursor.execute("""
            UPDATE PCs 
            SET is_available = 1 
            WHERE pc_name = 'PC-12' AND 
                  lab_id IN (SELECT id FROM Labs WHERE lab_name IN ('523', '524'))
        """)
        print(f"Updated {cursor.rowcount} PC-12 records in PCs table")
        
        # If no update happened, check if the records exist
        if cursor.rowcount == 0:
            print("PC-12 records might not exist, checking...")
            
            cursor.execute("SELECT id FROM Labs WHERE lab_name = '523'")
            lab_523_id = cursor.fetchone()
            cursor.execute("SELECT id FROM Labs WHERE lab_name = '524'")
            lab_524_id = cursor.fetchone()
            
            if lab_523_id:
                lab_523_id = lab_523_id[0]
                cursor.execute("SELECT id FROM PCs WHERE lab_id = ? AND pc_name = 'PC-12'", (lab_523_id,))
                pc_523 = cursor.fetchone()
                
                if not pc_523:
                    print("Creating PC-12 for lab 523...")
                    cursor.execute(
                        "INSERT INTO PCs (lab_id, pc_name, is_available) VALUES (?, 'PC-12', 1)",
                        (lab_523_id,)
                    )
                    print("PC-12 created for lab 523")
                else:
                    print(f"PC-12 exists for lab 523, ID: {pc_523[0]}")
            
            if lab_524_id:
                lab_524_id = lab_524_id[0]
                cursor.execute("SELECT id FROM PCs WHERE lab_id = ? AND pc_name = 'PC-12'", (lab_524_id,))
                pc_524 = cursor.fetchone()
                
                if not pc_524:
                    print("Creating PC-12 for lab 524...")
                    cursor.execute(
                        "INSERT INTO PCs (lab_id, pc_name, is_available) VALUES (?, 'PC-12', 1)",
                        (lab_524_id,)
                    )
                    print("PC-12 created for lab 524")
                else:
                    print(f"PC-12 exists for lab 524, ID: {pc_524[0]}")
        
        # 3. End any current reservations for PC-12
        cursor.execute("""
            UPDATE Reservation
            SET status = 'Ended', time_out = datetime('now')
            WHERE available_pc = 'PC-12' AND 
                  lab IN ('523', '524') AND
                  status IN ('Pending', 'Approved', 'Sit-in')
        """)
        print(f"Ended {cursor.rowcount} active reservations for PC-12")
        
        # 4. Delete any invalid reservations
        cursor.execute("""
            DELETE FROM Reservation
            WHERE available_pc = 'PC-12' AND
                  lab IN ('523', '524') AND
                  student_id IS NULL
        """)
        print(f"Deleted {cursor.rowcount} invalid reservations for PC-12")
        
        # 5. Force update by raw SQL to ensure it works
        try:
            cursor.execute("""
                UPDATE PCs 
                SET is_available = 1 
                WHERE pc_name = 'PC-12' AND 
                      lab_id IN (SELECT id FROM Labs WHERE lab_name IN ('523', '524'))
            """)
            conn.commit()
            print("Committed force update to database")
        except sqlite3.Error as e:
            print(f"Error in force update: {e}")
        
        # Commit all changes
        conn.commit()
        print("All database changes committed successfully")
        
        # Verify the changes
        print("\nVerifying PC-12 status in the database:")
        cursor.execute("""
            SELECT l.lab_name, p.pc_name, p.is_available 
            FROM PCs p 
            JOIN Labs l ON p.lab_id = l.id 
            WHERE p.pc_name = 'PC-12' AND l.lab_name IN ('523', '524')
        """)
        results = cursor.fetchall()
        
        if results:
            for lab_name, pc_name, is_available in results:
                print(f"Lab: {lab_name}, PC: {pc_name}, Available: {'Yes' if is_available else 'No'}")
        else:
            print("No PC-12 records found for labs 523/524 after update!")
        
        # Close the connection
        conn.close()
        print("Database connection closed\n")
        
    except Exception as e:
        print(f"Error updating database: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def restart_flask_app():
    """Attempt to restart the Flask application"""
    print("=== Attempting to restart Flask application ===")
    print("Note: This won't work if the application is running as a service or in a different environment")
    
    try:
        print("Looking for Flask process...")
        # This command varies by OS, this is a Windows example
        result = subprocess.run(
            ['tasklist', '/fi', 'imagename eq python.exe'], 
            capture_output=True, 
            text=True
        )
        
        print("Active Python processes:")
        print(result.stdout)
        
        print("\nThis script can't automatically restart the Flask app.")
        print("Please manually restart the application by:")
        print("1. Stopping the current Flask application")
        print("2. Starting it again using: python app.py\n")
        
    except Exception as e:
        print(f"Error checking Flask process: {str(e)}")

def main():
    """Main function to fix PC-12 issues"""
    print("=== PC-12 Availability Fix Script ===")
    print("This script will fix PC-12 showing as Reserved in labs 523 and 524\n")
    
    success = reset_database_tables()
    
    if success:
        print("\nDatabase updated successfully!")
        restart_flask_app()
        
        print("\n=== Instructions to complete the fix ===")
        print("1. Restart the Flask application")
        print("2. Refresh the lab control page in your browser")
        print("3. PC-12 should now show as Available for both labs 523 and 524")
    else:
        print("\nFailed to update database. Please check the error messages above.")
    
    print("\nScript completed.")

if __name__ == "__main__":
    main() 