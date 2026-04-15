// Copyright (c) 2026, Nakoda and contributors
// For license information, please see license.txt

frappe.ui.form.on("Nakoda Ledger Day", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.ledger_rows && frm.doc.ledger_rows.length > 0) {
			frm.add_custom_button(__('Review & Correct'), () => {
				const url = window.location.origin + '/app/ledger_review/' + frm.doc.name;
				window.open(url, '_blank');
			}, __('Actions'));

			// Check if this was just imported (flagged in session or check for just saved)
			if (frm.doc.__just_imported) {
				delete frm.doc.__just_imported;
				const url = window.location.origin + '/app/ledger_review/' + frm.doc.name;
				window.open(url, '_blank');
			}
		}

		// Existing View Report button (if any was intended in previous conversations)
		frm.add_custom_button(__('View Static Report'), () => {
			let d = new frappe.ui.Dialog({
				title: __('Import Report'),
				fields: [
					{
						fieldname: 'report_html',
						fieldtype: 'HTML'
					}
				]
			});
			d.fields_dict.report_html.$wrapper.html(frm.doc.import_log);
			d.show();
			d.wrapper.querySelector('.modal-dialog').style.maxWidth = '90vw';
		}, __('Actions'));
	},
});
