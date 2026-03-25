import frappe
def execute():
    query = """
        SELECT 
            c.custom_village as village, 
            COALESCE(SUM(gle.debit - gle.credit), 0) as outstanding,
            COUNT(DISTINCT c.name) as customer_count
        FROM `tabCustomer` c
        LEFT JOIN `tabGL Entry` gle ON gle.party = c.name AND gle.party_type = 'Customer' AND gle.is_cancelled = 0
        WHERE c.disabled = 0 AND IFNULL(c.custom_village, '') != ''
        GROUP BY c.custom_village
        ORDER BY outstanding DESC, customer_count DESC
    """
    res = frappe.db.sql(query, as_dict=True)
    print("NEW EXPOSURE:", res)
