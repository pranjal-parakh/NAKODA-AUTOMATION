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
    """Village-wise outstanding distribution and active customer tracking."""
    return frappe.db.sql("""
        SELECT 
            c.custom_village as village, 
            COALESCE(SUM(gle.debit - gle.credit), 0) as outstanding,
            COUNT(DISTINCT c.name) as customer_count
        FROM `tabCustomer` c
        LEFT JOIN `tabGL Entry` gle ON gle.party = c.name AND gle.party_type = 'Customer' AND gle.is_cancelled = 0
        WHERE c.disabled = 0 AND IFNULL(c.custom_village, '') != ''
        GROUP BY c.custom_village
        ORDER BY outstanding DESC, customer_count DESC
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
def get_recent_transactions(limit=10, start=0):
    """Unified chronological recent entries with names and pagination."""
    from frappe.utils import cint
    l = cint(limit) or 10
    s = cint(start) or 0
    
    return frappe.db.sql(f"""
        SELECT si.name, si.posting_date, si.creation, 'Udhaari' as type, si.customer, c.customer_name, si.grand_total as amount
        FROM `tabSales Invoice` si
        LEFT JOIN `tabCustomer` c ON si.customer = c.name
        WHERE si.docstatus = 1
        UNION ALL
        SELECT pe.name, pe.posting_date, pe.creation, 'Jama' as type, pe.party as customer, c.customer_name, pe.paid_amount as amount
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabCustomer` c ON pe.party = c.name
        WHERE pe.docstatus = 1 AND pe.party_type = 'Customer'
        ORDER BY posting_date DESC, creation DESC
        LIMIT {l} OFFSET {s}
    """, as_dict=1)

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
            "phone": customer.mobile_no,
            "reference_name": customer.reference_name,
            "local_address": customer.local_address,
            "custom_village": customer.custom_village
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
        WHERE (customer_name LIKE %s OR custom_village LIKE %s OR mobile_no LIKE %s)
        AND disabled = 0
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%"), as_dict=1)

@frappe.whitelist()
def get_village_ledger(village):
    """Village specific drilldown."""
    customers = frappe.db.sql("""
        SELECT 
            c.name,
            c.customer_name,
            c.reference_name,
            SUM(si.outstanding_amount) as outstanding,
            (SELECT MAX(posting_date) FROM `tabPayment Entry` WHERE party=c.name AND docstatus=1) as last_payment,
            SUM(si.grand_total) as total_borrowed
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Invoice` si ON c.name = si.customer AND si.docstatus = 1
        WHERE c.custom_village = %s
        GROUP BY c.name
        ORDER BY c.customer_name ASC
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
            c.reference_name,
            (SELECT COALESCE(SUM(debit - credit), 0) FROM `tabGL Entry` WHERE party=c.name AND is_cancelled=0) as outstanding,
            (SELECT MAX(posting_date) FROM `tabPayment Entry` WHERE party=c.name AND docstatus=1) as last_payment,
            COALESCE(SUM(si.grand_total), 0) as total_borrowed
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Invoice` si ON c.name = si.customer AND si.docstatus = 1
        WHERE c.disabled = 0
        GROUP BY c.name
        ORDER BY c.customer_name ASC
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
    
    frappe.response['type'] = 'binary'

@frappe.whitelist()
def get_account_receivables_report():
    """Generates the Account Receivables report data using total net outstanding (Pending Amount)."""
    data = frappe.db.sql("""
        SELECT 
            c.customer_name,
            c.reference_name,
            c.custom_village as village,
            c.mobile_no as phone,
            (SELECT SUM(debit - credit) 
             FROM `tabGL Entry` 
             WHERE party = c.name AND party_type = 'Customer' AND is_cancelled = 0) as amount_due,
            DATEDIFF(CURDATE(), 
                     (SELECT MAX(posting_date) FROM `tabGL Entry` 
                      WHERE party = c.name AND party_type = 'Customer' AND is_cancelled = 0 AND credit > 0)
            ) as days_since_last_payment,
            DATEDIFF(CURDATE(), 
                     (SELECT MIN(posting_date) FROM `tabGL Entry` 
                      WHERE party = c.name AND party_type = 'Customer' AND is_cancelled = 0 AND debit > 0)
            ) as age_days
        FROM `tabCustomer` c
        WHERE c.disabled = 0
        HAVING amount_due > 0
        ORDER BY c.custom_village ASC, amount_due DESC
    """, as_dict=1)
    
    return data



