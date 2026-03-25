import frappe
from nakoda_automation.dashboard import get_village_exposure
def execute():
    try:
        data = get_village_exposure()
        print("EXPOSURE DATA:")
        print(data)
    except Exception as e:
        print("ERROR:", e)
