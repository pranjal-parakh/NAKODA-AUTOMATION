frappe.pages['ocr-test'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'OCR Test',
		single_column: true
	});
}