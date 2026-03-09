import frappe
import os
import shutil

def run():
    print("Starting page registration...")
    pages = [
        {"name": "nakoda", "title": "Nakoda Control Center", "module": "Nakoda Automation"},
        {"name": "customer_profile", "title": "Customer Profile", "module": "Nakoda Automation"},
        {"name": "village_ledger", "title": "Village Ledger", "module": "Nakoda Automation"}
    ]
    
    for p in pages:
        if not frappe.db.exists("Page", p["name"]):
            doc = frappe.new_doc("Page")
            doc.page_name = p["name"]
            doc.title = p["title"]
            doc.module = p["module"]
            doc.standard = "Yes"
            doc.insert(ignore_permissions=True)
            print(f"Created Dashboard Page: {p['name']}")
        else:
            print(f"Page already exists: {p['name']}")
            
    if not frappe.db.exists("Role", "Nakoda Owner"):
        role = frappe.new_doc("Role")
        role.role_name = "Nakoda Owner"
        role.desk_access = 1
        role.insert(ignore_permissions=True)
        print("Created Role: Nakoda Owner")

    for p in pages:
        doc = frappe.get_doc("Page", p["name"])
        doc.roles = []
        doc.append("roles", {"role": "Nakoda Owner"})
        doc.append("roles", {"role": "System Manager"})
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        print(f"Assigned roles to {p['name']}")
        
    frappe.db.commit()
    print("Dashboard pages and roles configured successfully.")

    # Clean up old dashed folders that break Frappe routing
    base_dir = "/Users/pranjalparakh/nakoda-bench/apps/nakoda_automation/nakoda_automation/page"
    for d in ["customer-profile", "village-ledger"]:
        path = os.path.join(base_dir, d)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                print(f"Removed unused folder {path}")
            except Exception as e:
                print(f"Could not remove {path}: {e}")
