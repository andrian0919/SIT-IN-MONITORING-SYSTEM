from app import app

# Print all registered routes to diagnose the issue
print("===== REGISTERED ROUTES =====")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule.rule}, Methods: {rule.methods}")

# Check specifically for the add_points route
add_points_found = False
for rule in app.url_map.iter_rules():
    if rule.endpoint == 'add_points':
        add_points_found = True
        print(f"\nFound add_points route: {rule.rule}")
        print(f"Methods: {rule.methods}")

if not add_points_found:
    print("\nWARNING: add_points route is not registered correctly!")
    print("This explains the 404 error you're experiencing.")
    print("Please ensure the function is correctly defined in app.py with the @app.route decorator.") 