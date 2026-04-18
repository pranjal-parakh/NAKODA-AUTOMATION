frappe.pages['account_receivables'].on_page_load = function (wrapper) {
	new NakodaAccountReceivables(wrapper);
}

class NakodaAccountReceivables {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Account Receivables'),
			single_column: true
		});
		this.rows = [];
		this.init();
	}

	async init() {
		this.setup_styles();
		await this.load_data();
		this.render();
	}

	setup_styles() {
		const css = `
			.ledger-review-container { padding: 15px; background: #fff; }
			.review-header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
			.header-main { font-weight: bold; font-size: 1.1rem; margin-bottom: 5px; }
			.header-sub { font-size: 0.95rem; color: #888; }

			.section-title { font-weight: bold; margin-top: 25px; margin-bottom: 10px; font-size: 1rem; display: block; }
			
			.review-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; white-space: nowrap; margin-top: 8px; }
			.review-table th { padding: 6px 8px; text-align: left; border: 1px solid #ccc; background: #f8f9fa; font-weight: 600; }
			.review-table td { padding: 5px 8px; border: 1px solid #ccc; vertical-align: middle; }
			
			.row-item:hover { background: #f0f4f8; }

			.score-high { color: green; font-weight: 700; }
			.score-medium { color: orange; font-weight: 700; }
			.score-low { color: red; font-weight: 700; }
			
			.total-row td { padding: 8px 12px; border: 1px solid #ccc; font-weight: 700; }
		`;
		if (!$('#ledger-review-styles').length) {
			$('<style id="ledger-review-styles">').html(css).appendTo('head');
		}
	}

	async load_data() {
		frappe.dom.freeze(__('Loading Report...'));
		try {
			const r = await frappe.call({
				method: 'nakoda_automation.dashboard.get_account_receivables_report'
			});
			this.rows = r.message || [];
		} finally {
			frappe.dom.unfreeze();
		}
	}

	render() {
		const total_records = this.rows.length;
		let total_amount = 0;
		this.rows.forEach(r => total_amount += flt(r.amount_due));

		this.page.main.html(`
			<div class="ledger-review-container">
				<div class="review-header">
					<div class="header-main">Account Receivables Report</div>
					<div class="header-sub">
                        Total Customers: ${total_records} &nbsp;|&nbsp; 
                        Total Outstanding: ${format_currency(total_amount, 'INR', 0)}
                    </div>
				</div>

				<div class="section-title" style="color: red;">📉 Account Receivables</div>
				${this.render_table(this.rows)}
				
				<div style="height: 100px;"></div>
			</div>
		`);

		this.page.clear_primary_action();
		this.page.set_primary_action(__('Refresh'), () => {
			this.init();
		});

		this.page.add_inner_button(__('Print PDF'), () => {
			this.print_report();
		});
	}

	print_report() {
		const html = this.page.main.html();
		const w = window.open();
		w.document.write(`
			<html>
				<head>
					<title>Account Receivables Report - ${frappe.datetime.now_date()}</title>
					<style>
						@page {
							size: landscape;
							margin: 10mm;
						}
						body { 
							font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
							margin: 0;
							color: #333;
						}
						.ledger-review-container { padding: 0; }
						.review-header { margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px; }
						.header-main { font-weight: bold; font-size: 1.4rem; }
						.header-sub { font-size: 1rem; color: #555; }
						.section-title { font-weight: bold; margin-top: 20px; margin-bottom: 10px; font-size: 1.1rem; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
						
						.review-table { width: 100%; border-collapse: collapse; font-size: 10pt; table-layout: auto; }
						.review-table th { background: #eee !important; color: #000 !important; border: 1px solid #000; padding: 8px; text-align: left; -webkit-print-color-adjust: exact; }
						.review-table td { border: 1px solid #000; padding: 6px 8px; vertical-align: middle; }
						.total-row td { background: #f9f9f9 !important; font-weight: bold; border-top: 2px solid #000; -webkit-print-color-adjust: exact; }
						
						.text-right { text-align: right; }
						.text-center { text-align: center; }
						
						/* Hide anything that shouldn't be printed */
						.btn, .page-actions, .footer-help { display: none !important; }
						
						/* Remove horizontal scroll container from print */
						div[style*="overflow-x:auto"] { overflow: visible !important; }
					</style>
				</head>
				<body>
					${html}
					<div style="margin-top: 20px; font-size: 8pt; color: #888;">
						Printed on: ${frappe.datetime.now_datetime()}
					</div>
				</body>
			</html>
		`);
		w.document.close();
		
		// Give it a tiny moment to render
		setTimeout(() => {
			w.print();
			// w.close(); // Optional: close window after printing
		}, 500);
	}

	render_table(rows) {
		if (!rows.length) return `<div class="text-muted" style="font-size: 0.88rem; margin-left: 10px;">No records found</div>`;

		let html = `
            <div style="overflow-x:auto; width:100%;">
                <table class="review-table">
                    <thead>
                        <tr>
                            <th width="40">#</th>
                            <th width="180">Customer Name</th>
                            <th width="140">Reference Name</th>
                            <th width="120">Village</th>
                            <th width="120">Phone Number</th>
                            <th width="120" class="text-right">Amount Due</th>
                            <th width="100" class="text-center">Days Since</th>
                            <th width="100" class="text-center">Age Days</th>
                        </tr>
                    </thead>
                    <tbody>
		`;

		let total_amt = 0;
		rows.forEach((r, idx) => {
			total_amt += flt(r.amount_due);

			html += `
				<tr class="row-item">
					<td style="color: #555;">${idx + 1}</td>
					<td><b>${r.customer_name || '—'}</b></td>
					<td style="color: #666;">${r.reference_name || '—'}</td>
					<td>${r.village || '—'}</td>
					<td>${r.phone || '—'}</td>
					<td class="text-right" style="font-weight: 600; color: ${r.amount_due > 0 ? 'red' : 'inherit'};">${format_currency(r.amount_due, 'INR', 0)}</td>
					<td class="text-center">${r.days_since_last_payment !== null ? r.days_since_last_payment + ' d' : '—'}</td>
					<td class="text-center">${r.age_days !== null ? r.age_days + ' d' : '—'}</td>
				</tr>
			`;
		});

		html += `
			<tr class="total-row">
                <td colspan="5" style="text-align: right;">Total</td>
                <td style="text-align: right; color: red;">${format_currency(total_amt, 'INR', 0)}</td>
                <td colspan="2"></td>
            </tr>
        `;

		html += `</tbody></table></div>`;
		return html;
	}
}


