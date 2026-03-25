import frappe
from nakoda_automation.dashboard import get_dashboard_metrics

def execute():
    metrics = get_dashboard_metrics()
    print("METRICS:", metrics)
    raw = frappe.db.sql("SELECT c.custom_village, c.local_address, SUM(gle.debit - gle.credit) FROM `tabGL Entry` gle JOIN `tabCustomer` c ON gle.party = c.name WHERE gle.party_type = 'Customer' GROUP BY c.custom_village, c.local_address")
    print("RAW:", raw)
