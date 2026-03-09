import frappe

def delete_faulty_records():
    customers_to_delete = [
        "मदन सत.(30000+ब्याज-1000)",
        "चेतन लाल वर्मा(फौजी)(बाला)",
        "Unknown - S/51",
        "Unknown - S/49",
        "Unknown - S/47",
        "Unknown - 97",
        "Unknown - 92",
        "Unknown - 91",
        "Unknown - 1"
    ]

    for customer_name in customers_to_delete:
        print(f"--- Processing Customer: {customer_name} ---")
        
        # 1. Find all Sales Invoices for this customer
        invoices = frappe.get_all("Sales Invoice", filters={"customer": customer_name}, fields=["name", "docstatus"])
        for inv in invoices:
            try:
                # Cancel if submitted
                if inv.docstatus == 1:
                    doc = frappe.get_doc("Sales Invoice", inv.name)
                    doc.cancel()
                    print(f"Cancelled Invoice: {inv.name}")
                
                # Delete
                frappe.delete_doc("Sales Invoice", inv.name)
                print(f"Deleted Invoice: {inv.name}")
            except Exception as e:
                print(f"Error handling Invoice {inv.name}: {str(e)}")

        # 2. Find all Payment Entries for this customer
        payments = frappe.get_all("Payment Entry", filters={"party": customer_name, "party_type": "Customer"}, fields=["name", "docstatus"])
        for pe in payments:
            try:
                if pe.docstatus == 1:
                    doc = frappe.get_doc("Payment Entry", pe.name)
                    doc.cancel()
                    print(f"Cancelled Payment: {pe.name}")
                
                frappe.delete_doc("Payment Entry", pe.name)
                print(f"Deleted Payment: {pe.name}")
            except Exception as e:
                print(f"Error handling Payment {pe.name}: {str(e)}")

        # 3. Find any remaining GL Entries (though cancelling invoices should handle most)
        # We generally don't delete GL entries directly, we cancel the parent.
        # But if there are lingering ones, they might block.

        # 4. Finally delete the customer
        if frappe.db.exists("Customer", customer_name):
            try:
                frappe.delete_doc("Customer", customer_name)
                print(f"SUCCESS: Deleted Customer {customer_name}")
            except Exception as e:
                print(f"FAILED: Could not delete Customer {customer_name}. Error: {str(e)}")
        
        frappe.db.commit()

if __name__ == "__main__":
    delete_faulty_records()
