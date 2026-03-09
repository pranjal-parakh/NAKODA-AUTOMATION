import frappe

def run():
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
            doc.standard = 1 # Standard 1 ensures it reads from the file system (.js, .json)
            doc.insert(ignore_permissions=True)
            print("Created:", p["name"])
        else:
            print("Exists:", p["name"])
            
    # Assign Roles
    if not frappe.db.exists("Role", "Nakoda Owner"):
        frappe.get_doc({"doctype": "Role", "role_name": "Nakoda Owner", "desk_access": 1}).insert(ignore_permissions=True)
        print("Created Role: Nakoda Owner")
        
    for p in pages:
        page_doc = frappe.get_doc("Page", p["name"])
        page_doc.roles = []
        page_doc.append("roles", {"role": "Nakoda Owner"})
        page_doc.append("roles", {"role": "System Manager"})
        page_doc.flags.ignore_permissions = True
        page_doc.save(ignore_permissions=True)
        print(f"Roles assigned for: {p['name']}")

    frappe.db.commit()
    print("Dashboard pages successfully registered!")
