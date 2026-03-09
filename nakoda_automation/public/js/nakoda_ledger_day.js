frappe.ui.form.on('Nakoda Ledger Day', {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            // Already created, hide the upload button if parsing is done
            if (frm.doc.rows_processed > 0 || frm.doc.rows_failed > 0) {
                return;
            }
        }
        
        frm.add_custom_button(__('Process Excel'), function() {
            if (!frm.doc.excel_file) {
                frappe.msgprint(__('Please attach an Excel file first.'));
                return;
            }
            
            frappe.call({
                method: 'nakoda_automation.ledger_sync.api.upload_excel_ledger',
                args: {
                    file_url: frm.doc.excel_file
                },
                freeze: true,
                freeze_message: __('Parsing and Uploading Ledger...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('Success'),
                            indicator: 'green',
                            message: r.message.message
                        });
                        if (r.message.dashboard_id) {
                            frappe.set_route('Form', 'Nakoda Ledger Day', r.message.dashboard_id);
                        } else {
                            frm.reload_doc();
                        }
                    } else if (r.message && r.message.status === 'error') {
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: r.message.message
                        });
                        frm.reload_doc();
                    }
                }
            });
        }).addClass('btn-primary');
    }
});
