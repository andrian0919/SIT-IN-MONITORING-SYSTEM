from flask import Blueprint, request, jsonify, flash, redirect, url_for, session
from app import db

# Create a blueprint for resource routes
resource_bp = Blueprint('resource_routes', __name__)

@resource_bp.route("/disable/<int:resource_id>", methods=["GET", "POST"])
def disable_resource(resource_id):
    """Disable a resource"""
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to disable resources", "danger")
        return redirect(url_for("home"))
    
    print(f"Disabling resource {resource_id}")
    
    try:
        # Use direct SQL to update the resource
        from sqlalchemy import text
        
        # First check if resource exists
        result = db.session.execute(
            text("SELECT id, title FROM Resources WHERE id = :id"),
            {"id": resource_id}
        ).fetchone()
        
        if not result:
            flash("Resource not found", "danger")
            return redirect(url_for("admin_resources"))
        
        # Update the status to disabled
        db.session.execute(
            text("UPDATE Resources SET status = 'disabled' WHERE id = :id"),
            {"id": resource_id}
        )
        db.session.commit()
        
        flash(f"Resource '{result[1]}' disabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error disabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources"))

@resource_bp.route("/enable/<int:resource_id>", methods=["GET", "POST"])
def enable_resource(resource_id):
    """Enable a resource"""
    if "user_id" not in session or session.get("role") != "admin":
        flash("You must be an admin to enable resources", "danger")
        return redirect(url_for("home"))
    
    print(f"Enabling resource {resource_id}")
    
    try:
        # Use direct SQL to update the resource
        from sqlalchemy import text
        
        # First check if resource exists
        result = db.session.execute(
            text("SELECT id, title FROM Resources WHERE id = :id"),
            {"id": resource_id}
        ).fetchone()
        
        if not result:
            flash("Resource not found", "danger")
            return redirect(url_for("admin_resources"))
        
        # Update the status to enabled
        db.session.execute(
            text("UPDATE Resources SET status = 'enabled' WHERE id = :id"),
            {"id": resource_id}
        )
        db.session.commit()
        
        flash(f"Resource '{result[1]}' enabled successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error enabling resource: {str(e)}", "danger")
    
    return redirect(url_for("admin_resources")) 