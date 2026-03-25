import frappe
from frappe import _
from frappe.utils import flt, getdate, today, nowdate

@frappe.whitelist()
def create_customer(name, phone=None, village=None):
    """Creates a new customer or updates an existing one."""
    if not name:
        frappe.throw(_("Customer Name is required"))
    
    # Check if customer already exists by name
    customer_name = frappe.db.get_value("Customer", {"customer_name": name}, "name")
    
    if not customer_name:
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
            "customer_type": "Individual",
            "mobile_no": phone,
            "custom_village": village
        })
        customer.insert(ignore_permissions=True)
        customer_name = customer.name
    else:
        # Update phone/village if provided
        customer = frappe.get_doc("Customer", customer_name)
        if phone: customer.mobile_no = phone
        if village: customer.custom_village = village
        customer.save(ignore_permissions=True)
        
    return get_customer_info(customer_name)

@frappe.whitelist()
def search_customer(query):
    """Search for customers by name, phone, or village."""
    return frappe.db.sql("""
        SELECT name, customer_name, mobile_no as phone, custom_village as village
        FROM `tabCustomer`
        WHERE (name LIKE %s OR customer_name LIKE %s OR mobile_no LIKE %s OR custom_village LIKE %s)
        AND disabled = 0
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"), as_dict=1)

@frappe.whitelist()
def get_customer_info(customer_name):
    """Returns basic customer info + outstanding balance."""
    customer = frappe.get_doc("Customer", customer_name)
    
    outstanding = frappe.db.sql("""
        SELECT SUM(outstanding_amount) 
        FROM `tabSales Invoice` 
        WHERE customer = %s AND docstatus = 1
    """, (customer_name,))[0][0] or 0
    
    return {
        "name": customer.name,
        "customer_name": customer.customer_name,
        "phone": customer.mobile_no,
        "village": customer.custom_village,
        "outstanding": outstanding
    }

@frappe.whitelist()
def get_villages():
    """Returns a list of all existing villages."""
    return [v.name for v in frappe.get_all("Village", fields=["name"], order_by="creation desc")]

@frappe.whitelist()
def create_udhaari_transaction(customer, date, amount):
    """Creates and submits a Sales Invoice."""
    amount = normalize_amount(amount)
    if amount <= 0:
        frappe.throw(_("Amount must be greater than zero"))
        
    # Ensure UDHAARI item exists
    if not frappe.db.exists("Item", "UDHAARI"):
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "UDHAARI",
            "item_name": "Udhaari",
            "item_group": "All Item Groups",
            "is_stock_item": 0,
            "stock_uom": "Nos"
        })
        item.insert(ignore_permissions=True)

    transaction_date = getdate(date) if date else getdate(today())
    
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": get_default_company(),
        "customer": customer,
        "items": [{
            "item_code": "UDHAARI",
            "qty": 1,
            "rate": amount
        }]
    })
    si.set_missing_values()
    si.payment_terms_template = ""
    si.ignore_default_payment_terms_template = 1
    si.set_posting_time = 1
    si.posting_date = transaction_date
    si.due_date = transaction_date
    si.insert(ignore_permissions=True)
    si.submit()
    
    return {"status": "success", "name": si.name}

@frappe.whitelist()
def create_jama_transaction(customer, date, amount):
    """Creates and submits a Payment Entry with explicit allocation."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_reference_documents
    
    amount = flt(normalize_amount(amount))
    if amount <= 0:
        frappe.throw(_("Amount must be greater than zero"))

    transaction_date = getdate(date) if date else getdate(today())
    company = get_default_company()
    
    # Explicitly fetch receivable account
    receivable_account = frappe.get_value(
        "Party Account",
        {"parent": customer, "company": company},
        "account"
    )
    if not receivable_account:
        receivable_account = frappe.get_cached_value(
            "Company", company, "default_receivable_account"
        )

    # 1. Fetch outstanding invoices
    outstanding = get_outstanding_reference_documents({
        "posting_date": transaction_date,
        "company": company,
        "party_type": "Customer",
        "party": customer,
        "party_account": receivable_account
    })

    # 2. Create Payment Entry
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "company": company,
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": customer,
        "posting_date": transaction_date,
        "paid_from": receivable_account,
        "paid_amount": amount,
        "received_amount": amount,
        "paid_to": get_default_bank_or_cash_account(),
    })
    
    pe.setup_party_account_field()
    pe.set_missing_values()

    # 3. Explicit Allocation
    remaining = amount
    if outstanding:
        for inv in outstanding:
            if remaining <= 0:
                break

            allocated = min(flt(inv.outstanding_amount), remaining)
            pe.append("references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": inv.voucher_no,
                "due_date": inv.due_date,
                "total_amount": inv.invoice_amount,
                "outstanding_amount": inv.outstanding_amount,
                "allocated_amount": allocated
            })
            remaining -= allocated

    # 4. Insert and Submit
    pe.insert(ignore_permissions=True)
    pe.submit()
    
    return {"status": "success", "name": pe.name}

@frappe.whitelist()
def get_customer_transactions(customer, limit=10):
    """Fetch last 10 entries for a customer."""
    # Fetch recent Sales Invoices (Udhaari)
    invoices = frappe.db.sql("""
        SELECT 
            name as id, posting_date as date, 'Udhaari' as type, grand_total as amount
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
        ORDER BY creation DESC
        LIMIT %s
    """, (customer, limit), as_dict=1)

    # Fetch recent Payment Entries (Jama)
    payments = frappe.db.sql("""
        SELECT 
            name as id, posting_date as date, 'Jama' as type, paid_amount as amount
        FROM `tabPayment Entry`
        WHERE party = %s AND party_type = 'Customer' AND docstatus = 1
        ORDER BY creation DESC
        LIMIT %s
    """, (customer, limit), as_dict=1)
    
    combined = sorted(list(invoices) + list(payments), key=lambda x: x['date'], reverse=True)
    return combined[:limit]

def normalize_amount(amount_str):
    """Converts 12k to 12000, etc."""
    if isinstance(amount_str, (int, float)):
        return flt(amount_str)
        
    s = str(amount_str).strip().lower().replace(",", "")
    if s.endswith('k'):
        return flt(s[:-1]) * 1000
    return flt(s)

def get_default_bank_or_cash_account():
    """Returns a default account for receiving payments."""
    company = get_default_company()
    
    # 1. Try to get default Cash/Bank account from Company
    company_doc = frappe.get_doc("Company", company)
    if company_doc.default_cash_account: return company_doc.default_cash_account
    if company_doc.default_bank_account: return company_doc.default_bank_account
    
    # 2. Search for accounts with account_type 'Cash' or 'Bank'
    acc = frappe.db.get_value("Account", 
        {"account_type": ["in", ["Cash", "Bank"]], "company": company, "is_group": 0}, 
        "name", order_by="account_type desc")
    if acc: return acc
    
    # 3. Fallback to common names
    for name in ["Cash", "Bank", "Cash in Hand"]:
        acc = frappe.db.get_value("Account", {"account_name": name, "company": company}, "name")
        if acc: return acc
        
    frappe.throw(_("Please set a default Cash or Bank account in Company settings."))

def get_default_company():
    return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company")[0].name
