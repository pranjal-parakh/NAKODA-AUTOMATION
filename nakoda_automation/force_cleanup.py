import frappe

def force_delete_customer(customer_name):
    print(f"FORCING DELETE: {customer_name}")
    
    # 1. Get all Invoices
    invoices = frappe.get_all("Sales Invoice", filters={"customer": customer_name})
    for inv in invoices:
        print(f"Force deleting Invoice: {inv.name}")
        # Delete child tables
        frappe.db.sql(f"DELETE FROM `tabSales Invoice Item` WHERE parent='{inv.name}'")
        frappe.db.sql(f"DELETE FROM `tabSales Invoice` WHERE name='{inv.name}'")
        # Delete GL entries
        frappe.db.sql(f"DELETE FROM `tabGL Entry` WHERE voucher_no='{inv.name}'")

    # 2. Get all Payments
    payments = frappe.get_all("Payment Entry", filters={"party": customer_name, "party_type": "Customer"})
    for pe in payments:
        print(f"Force deleting Payment: {pe.name}")
        # Delete child tables
        frappe.db.sql(f"DELETE FROM `tabPayment Entry Reference` WHERE parent='{pe.name}'")
        frappe.db.sql(f"DELETE FROM `tabPayment Entry` WHERE name='{pe.name}'")
        # Delete GL entries
        frappe.db.sql(f"DELETE FROM `tabGL Entry` WHERE voucher_no='{pe.name}'")

    # 3. GL entries where customer is directly linked in party field
    frappe.db.sql(f"DELETE FROM `tabGL Entry` WHERE party='{customer_name}'")

    # 4. Finally delete the customer
    frappe.db.sql(f"DELETE FROM `tabCustomer` WHERE name='{customer_name}'")
    print(f"SUCCESS: Force removed {customer_name}")

def run_cleanup():
    target_customers = ["मदन सत.(30000+ब्याज-1000)", "चेतन लाल वर्मा(फौजी)(बाला)"]
    for c in target_customers:
        try:
            force_delete_customer(c)
        except Exception as e:
            print(f"Error force deleting {c}: {str(e)}")
    
    frappe.db.commit()

if __name__ == "__main__":
    run_cleanup()
