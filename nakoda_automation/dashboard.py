import frappe
from frappe import _
from frappe.utils import getdate, today, add_days

@frappe.whitelist()
def get_dashboard_metrics():
    """Returns top health KPIs for the business."""
    # 1. Total Outstanding (Net receivable from all customers)
    total_outstanding = frappe.db.sql("""
        SELECT SUM(debit - credit) 
        FROM `tabGL Entry` 
        WHERE party_type = 'Customer' AND is_cancelled = 0
    """)[0][0] or 0

    # 2. Total Udhaari Today (Sum of Sales Invoices today)
    today_udhaari = frappe.db.sql("""
        SELECT SUM(grand_total) 
        FROM `tabSales Invoice` 
        WHERE posting_date = %s AND docstatus = 1
    """, (today(),))[0][0] or 0

    # 3. Total Jama Today (Sum of Payment Entries today)
    today_jama = frappe.db.sql("""
        SELECT SUM(paid_amount) 
        FROM `tabPayment Entry` 
        WHERE posting_date = %s AND docstatus = 1 AND party_type = 'Customer'
    """, (today(),))[0][0] or 0

    # 4. Total Overdue
    total_overdue = frappe.db.sql("""
        SELECT SUM(outstanding_amount) 
        FROM `tabSales Invoice` 
        WHERE docstatus = 1 AND due_date < %s AND outstanding_amount > 0
    """, (today(),))[0][0] or 0

    # 5. Active Customers (Count of customers with outstanding > 0)
    active_customers = frappe.db.sql("""
        SELECT COUNT(DISTINCT customer) 
        FROM `tabSales Invoice` 
        WHERE docstatus = 1 AND outstanding_amount > 0
    """)[0][0] or 0

    return {
        "total_outstanding": total_outstanding,
        "today_udhaari": today_udhaari,
        "today_jama": today_jama,
        "total_overdue": total_overdue,
        "active_customers": active_customers
    }

@frappe.whitelist()
def get_village_exposure():
    """Village-wise outstanding distribution."""
    return frappe.db.sql("""
        SELECT 
            c.custom_village as village, 
            SUM(gle.debit - gle.credit) as outstanding,
            COUNT(DISTINCT gle.party) as customer_count
        FROM `tabGL Entry` gle
        JOIN `tabCustomer` c ON gle.party = c.name
        WHERE gle.party_type = 'Customer' AND gle.is_cancelled = 0
        GROUP BY c.custom_village
        HAVING outstanding > 0
        ORDER BY outstanding DESC
    """, as_dict=1)

@frappe.whitelist()
def get_top_debtors(limit=5):
    """Top customers by outstanding amount."""
    return frappe.db.sql("""
        SELECT 
            party as name, 
            SUM(debit - credit) as outstanding
        FROM `tabGL Entry`
        WHERE party_type = 'Customer' AND is_cancelled = 0
        GROUP BY party
        HAVING outstanding > 0
        ORDER BY outstanding DESC
        LIMIT %s
    """, (limit,), as_dict=1)

@frappe.whitelist()
def get_recent_transactions(limit=10):
    """Unified chronological recent entries."""
    # Fetch recent Sales Invoices (Udhaari)
    invoices = frappe.db.sql("""
        SELECT 
            name, posting_date, 'Udhaari' as type, customer, grand_total as amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1
        ORDER BY posting_date DESC
        LIMIT %s
    """, (limit,), as_dict=1)

    # Fetch recent Payment Entries (Jama)
    payments = frappe.db.sql("""
        SELECT 
            name, posting_date, 'Jama' as type, party as customer, paid_amount as amount
        FROM `tabPayment Entry`
        WHERE docstatus = 1 AND party_type = 'Customer'
        ORDER BY posting_date DESC
        LIMIT %s
    """, (limit,), as_dict=1)
    
    # Combined and sorted by transaction date (posting_date)
    combined = sorted(list(invoices) + list(payments), key=lambda x: x['posting_date'], reverse=True)
    return combined[:limit]

@frappe.whitelist()
def get_customer_profile(customer_name):
    """Full detail for customer profile page."""
    # Basic data
    customer = frappe.get_doc("Customer", customer_name)
    
    # Financial aggregate
    finance = frappe.db.sql("""
        SELECT 
            SUM(grand_total) as total_borrowed,
            (SELECT SUM(paid_amount) FROM `tabPayment Entry` WHERE party=%s AND docstatus=1 AND party_type='Customer') as total_repaid,
            (SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE party=%s AND is_cancelled=0) as outstanding,
            (SELECT MAX(posting_date) FROM `tabPayment Entry` WHERE party=%s AND docstatus=1 AND party_type='Customer') as last_payment_date,
            (SELECT MIN(due_date) FROM `tabSales Invoice` WHERE customer=%s AND docstatus=1 AND outstanding_amount > 0) as next_due_date
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
    """, (customer_name, customer_name, customer_name, customer_name, customer_name), as_dict=1)
    
    finance = finance[0] if finance else {}

    return {
        "info": {
            "name": customer.name,
            "customer_name": customer.customer_name,
            "village": customer.custom_village,
            "phone": customer.mobile_no
        },
        "metrics": finance
    }

@frappe.whitelist()
def get_customer_ledger(customer_name):
    """Timeline of all transactions."""
    return frappe.db.sql("""
        (SELECT posting_date, 'Udhaari' as type, name as id, grand_total as amount 
         FROM `tabSales Invoice` WHERE customer=%s AND docstatus=1)
        UNION ALL
        (SELECT posting_date, 'Jama' as type, name as id, paid_amount as amount 
         FROM `tabPayment Entry` WHERE party=%s AND docstatus=1 AND party_type='Customer')
        ORDER BY posting_date ASC
    """, (customer_name, customer_name), as_dict=1)

@frappe.whitelist()
def get_customer_invoices(customer_name):
    """Active and past invoices for detail panel."""
    return frappe.get_all("Sales Invoice", 
        filters={"customer": customer_name, "docstatus": 1},
        fields=["name", "posting_date", "grand_total", "due_date", "outstanding_amount"],
        order_by="posting_date desc"
    )

@frappe.whitelist()
def get_customer_payments(customer_name):
    """Check payment history."""
    return frappe.db.sql("""
        SELECT pe.posting_date, pe.name, pe.paid_amount,
               (SELECT GROUP_CONCAT(reference_name) FROM `tabPayment Entry Reference` WHERE parent=pe.name) as references
        FROM `tabPayment Entry` pe
        WHERE pe.party = %s AND pe.party_type = 'Customer' AND pe.docstatus = 1
        ORDER BY pe.posting_date DESC
    """, (customer_name,), as_dict=1)

@frappe.whitelist()
def search_customers(query):
    """Global search for dashboard."""
    return frappe.db.sql("""
        SELECT name, customer_name, custom_village, mobile_no
        FROM `tabCustomer`
        WHERE (name LIKE %s OR customer_name LIKE %s OR custom_village LIKE %s OR mobile_no LIKE %s)
        AND disabled = 0
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"), as_dict=1)

@frappe.whitelist()
def get_village_ledger(village):
    """Village specific drilldown."""
    customers = frappe.db.sql("""
        SELECT 
            c.name,
            SUM(si.outstanding_amount) as outstanding,
            (SELECT MAX(posting_date) FROM `tabPayment Entry` WHERE party=c.name AND docstatus=1) as last_payment,
            SUM(si.grand_total) as total_borrowed
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Invoice` si ON c.name = si.customer AND si.docstatus = 1
        WHERE c.custom_village = %s
        GROUP BY c.name
        ORDER BY outstanding DESC
    """, (village,), as_dict=1)
    
    summary = {
        "total_exposure": sum(c['outstanding'] or 0 for c in customers),
        "total_customers": len(customers)
    }
    
    return {
        "customers": customers,
        "summary": summary
    }

@frappe.whitelist()
def get_all_customers():
    """Returns all customers with their metrics."""
    customers = frappe.db.sql("""
        SELECT 
            c.name,
            c.customer_name,
            c.custom_village as village,
            c.mobile_no as phone,
            (SELECT COALESCE(SUM(debit - credit), 0) FROM `tabGL Entry` WHERE party=c.name AND is_cancelled=0) as outstanding,
            (SELECT MAX(posting_date) FROM `tabPayment Entry` WHERE party=c.name AND docstatus=1) as last_payment,
            COALESCE(SUM(si.grand_total), 0) as total_borrowed
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Invoice` si ON c.name = si.customer AND si.docstatus = 1
        WHERE c.disabled = 0
        GROUP BY c.name
        ORDER BY outstanding DESC
    """, as_dict=1)
    
    summary = {
        "total_exposure": sum(c['outstanding'] or 0 for c in customers),
        "total_customers": len(customers)
    }
    
    return {
        "customers": customers,
        "summary": summary
    }

@frappe.whitelist()
def export_village_exposure():
    """Generates an Excel report of village wise exposure."""
    data = get_village_exposure()
    
    from frappe.utils.xlsxutils import make_xlsx
    xlsx_file = make_xlsx([["Village", "Outstanding Amount"]] + [[d.village, d.outstanding] for d in data], "Village Exposure")
    
    frappe.response['filename'] = f"Village_Exposure_{today()}.xlsx"
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['type'] = 'binary'

@frappe.whitelist()
def export_customer_outstanding():
    """Generates an Excel report of all customer outstandings."""
    data = frappe.db.sql("""
        SELECT 
            c.customer_name, 
            c.custom_village, 
            SUM(si.outstanding_amount) as outstanding
        FROM `tabCustomer` c
        JOIN `tabSales Invoice` si ON c.name = si.customer
        WHERE si.docstatus = 1 AND si.outstanding_amount > 0
        GROUP BY c.name
        ORDER BY outstanding DESC
    """, as_dict=1)
    
    from frappe.utils.xlsxutils import make_xlsx
    xlsx_file = make_xlsx([["Customer", "Village", "Outstanding"]] + [[d.customer_name, d.custom_village, d.outstanding] for d in data], "Customer Outstanding")
    
    frappe.response['filename'] = f"Customer_Outstanding_{today()}.xlsx"
    frappe.response['filecontent'] = xlsx_file.getvalue()
    frappe.response['type'] = 'binary'

