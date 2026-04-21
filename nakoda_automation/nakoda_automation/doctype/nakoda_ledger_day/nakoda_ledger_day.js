frappe.ui.form.on("Nakoda Ledger Day", {
	refresh(frm) {
		const is_posted = frm.doc.rows_processed > 0;
		const has_rows = frm.doc.ledger_rows && frm.doc.ledger_rows.length > 0;
		const pending_count = frm.doc.ledger_rows ? frm.doc.ledger_rows.filter(r => r.status === 'Pending').length : 0;

		// 1. Primary Review & Correct Button (Swapped and Promoted)
		if (!is_posted && has_rows) {
			frm.add_custom_button(__('Review & Correct'), () => {
				frappe.set_route('ledger_review', frm.doc.name);
			}).addClass('btn-success');
		}

		// 2. Parse Excel Button (Moved to Actions group)
		if (frm.doc.excel_file && !is_posted) {
			frm.add_custom_button(__('Parse Excel Ledger'), function() {
				frappe.call({
					method: 'nakoda_automation.ledger_sync.api.parse_excel_ledger',
					args: {
						file_url: frm.doc.excel_file,
						dashboard_id: frm.doc.name
					},
					freeze: true,
					freeze_message: __('Parsing Excel & Resolving Customers...'),
					callback: function(r) {
						if (r.message && r.message.status === 'success') {
							// Immediate redirection, no success message as requested
							frappe.set_route('ledger_review', frm.doc.name);
						}
					}
				});
			}, __('Actions'));
		}

		// 3. Post Entries Button
		if (pending_count > 0 && !is_posted) {
			frm.add_custom_button(__('Post Ledger Entries'), function() {
				frappe.confirm(__('Are you sure you want to post these entries to the ERP ledger?'), () => {
					frappe.call({
						method: 'nakoda_automation.ledger_sync.api.post_ledger_entries',
						args: { dashboard_id: frm.doc.name },
						freeze: true,
						callback: function(r) {
							if (r.message && r.message.status === 'success') {
								frappe.msgprint(__('Entries posted successfully!'));
								frm.reload_doc();
							}
						}
					});
				});
			}, __('Actions'));
		}

		// 4. View Extraction Log (Restored to Actions)
		if (frm.doc.import_log) {
			frm.add_custom_button(__('View Extraction Log'), () => {
				let d = new frappe.ui.Dialog({
					title: __('Import Report'),
					fields: [{ fieldname: 'report_html', fieldtype: 'HTML' }]
				});
				d.fields_dict.report_html.$wrapper.html(frm.doc.import_log);
				d.show();
				d.wrapper.querySelector('.modal-dialog').style.maxWidth = '90vw';
			}, __('Actions'));
		}
	},
});
