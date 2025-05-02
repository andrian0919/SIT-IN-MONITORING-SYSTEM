"""
Direct Lab Schedule Rendering Script
This script bypasses all template logic and directly creates a fixed template
"""

from app import app, Lab, create_demo_schedules
from flask import render_template
from datetime import datetime

def fix_templates():
    with app.app_context():
        # Get all labs
        labs = Lab.query.all()
        
        # Get demo data
        demo_data = create_demo_schedules()
        
        # Create direct mapping
        lab_mapping = {
            "524": "Lab 524",
            "544": "Lab 544",
            "523": "Lab 523",
            "526": "Lab 526",
            "Mac lab": "Mac lab"
        }
        
        # Create direct mappings
        lab_schedules_data = {}
        for lab in labs:
            demo_key = lab_mapping.get(lab.lab_name, "Lab 524")
            lab_schedules_data[lab.lab_name] = demo_data.get(demo_key, [])
            
        # Generate HTML for each lab section
        lab_sections_html = ""
        
        # Print information
        print("Generated HTML sections for these labs:")
        
        # Process each lab except Mac lab
        for lab_name, schedules in lab_schedules_data.items():
            if lab_name != "Mac lab":
                print(f"- {lab_name}: {len(schedules)} schedules")
                
                # Start lab section
                section = f"""
                <div class="lab-section">
                    <h3 class="lab-title">{lab_name}</h3>
                """
                
                if schedules and len(schedules) > 0:
                    # Add table header
                    section += """
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
                    day_schedules = {}
                    
                    for day in days:
                        day_items = []
                        for schedule in schedules:
                            if schedule["day_of_week"] == day:
                                day_items.append(schedule)
                        
                        if day_items:
                            # Add day header
                            section += f"""
                            <tr class="day-label">
                                <td colspan="5">{day}</td>
                            </tr>
                            """
                            
                            # Add each schedule
                            for schedule in sorted(day_items, key=lambda x: x["start_time"]):
                                title_class = ""
                                if schedule["title"] == "Available":
                                    title_class = "status-available"
                                elif schedule["title"] == "Reserved":
                                    title_class = "status-reserved"
                                elif schedule["title"] == "Maintenance":
                                    title_class = "status-maintenance"
                                elif "Class" in schedule["title"]:
                                    title_class = "status-class"
                                    
                                section += f"""
                                <tr>
                                    <td></td>
                                    <td>{schedule["start_time"]} - {schedule["end_time"]}</td>
                                    <td>
                                        <span class="{title_class}">{schedule["title"]}</span>
                                        {'<br><small>' + schedule["description"] + '</small>' if schedule["description"] else ''}
                                    </td>
                                    <td>{schedule["max_capacity"]}</td>
                                    <td>{schedule["course"]}</td>
                                </tr>
                                """
                    
                    # Close table
                    section += """
                        </tbody>
                    </table>
                    """
                else:
                    section += """
                    <div class="no-schedules">
                        No schedules available for this lab.
                    </div>
                    """
                
                # Close lab section
                section += """
                </div>
                """
                
                lab_sections_html += section
        
        # Generate the Mac lab section
        mac_lab_html = ""
        if "Mac lab" in lab_schedules_data:
            mac_schedules = lab_schedules_data["Mac lab"]
            print(f"- Mac lab: {len(mac_schedules)} schedules")
            
            # Start Mac lab section
            mac_lab_html = """
            <div class="mac-lab-container">
                <div class="lab-section">
                    <h3 class="lab-title">Mac Lab</h3>
            """
            
            if mac_schedules and len(mac_schedules) > 0:
                # Add table header
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
                
                for day in days:
                    day_items = []
                    for schedule in mac_schedules:
                        if schedule["day_of_week"] == day:
                            day_items.append(schedule)
                    
                    if day_items:
                        # Add day header
                        mac_lab_html += f"""
                        <tr class="day-label">
                            <td colspan="5">{day}</td>
                        </tr>
                        """
                        
                        # Add each schedule
                        for schedule in sorted(day_items, key=lambda x: x["start_time"]):
                            title_class = ""
                            if schedule["title"] == "Available":
                                title_class = "status-available"
                            elif schedule["title"] == "Reserved":
                                title_class = "status-reserved"
                            elif schedule["title"] == "Maintenance":
                                title_class = "status-maintenance"
                            elif "Class" in schedule["title"]:
                                title_class = "status-class"
                                
                            mac_lab_html += f"""
                            <tr>
                                <td></td>
                                <td>{schedule["start_time"]} - {schedule["end_time"]}</td>
                                <td>
                                    <span class="{title_class}">{schedule["title"]}</span>
                                    {'<br><small>' + schedule["description"] + '</small>' if schedule["description"] else ''}
                                </td>
                                <td>{schedule["max_capacity"]}</td>
                                <td>{schedule["course"]}</td>
                            </tr>
                            """
                
                # Close table
                mac_lab_html += """
                    </tbody>
                </table>
                """
            else:
                mac_lab_html += """
                <div class="no-schedules">
                    No schedules available for this lab.
                </div>
                """
            
            # Close Mac lab section
            mac_lab_html += """
                </div>
            </div>
            """
        
        # Write the results to a file for review
        with open("fixed_lab_schedules.html", "w") as f:
            f.write(lab_sections_html)
            f.write(mac_lab_html)
        
        print("\nGenerated fixed HTML sections. To use them:")
        print("1. Replace the corresponding parts in templates/lab_schedules.html")
        print("2. Or directly serve this fixed HTML through a route")

if __name__ == "__main__":
    fix_templates() 