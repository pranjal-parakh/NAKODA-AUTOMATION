frappe.pages['ledger_review'].on_page_load = function (wrapper) {
	new NakodaLedgerReview(wrapper);
}

class NakodaLedgerReview {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Review:- नाकोड़ा जमा/उधार खाता'),
			single_column: true
		});
		this.dashboard_id = frappe.get_route()[1];
		this.ledger_day = null;
		this.rows = [];
		this.current_focus_index = 0;
		this.init();
	}

	async init() {
		this.setup_styles();
		if (!this.dashboard_id) {
			this.page.set_indicator(__('No Document Selected'), 'red');
			return;
		}
		await this.load_data();
		this.render();
		this.setup_keyboard_nav();
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
			
			.row-item { cursor: pointer; }
			.row-item:hover { background: #f0f4f8; }
			.row-item.active-row { background: #e2e8f0 !important; outline: 2px solid #4a90e2; outline-offset: -2px; }
			.row-item.corrected { background: #f0f9ff; }
			.row-item.corrected b { color: #007bff !important; }

			.score-high { color: green; font-weight: 700; }
			.score-medium { color: orange; font-weight: 700; }
			.score-low { color: red; font-weight: 700; }
			
			.vil-match { color: green; }
			.vil-mismatch { color: red; }
			
			.customer-cell { cursor: pointer; }
			.customer-cell:hover { background: #edf2f7; }
            
            .delete-cell { color: #ccc; cursor: pointer; text-align: center; font-size: 18px; line-height: 1; }
            .delete-cell:hover { color: #dc3545; }
			
			.footer-help { position: fixed; bottom: 0; left: 0; right: 0; background: #343a40; color: white; padding: 6px 20px; font-size: 11px; display: flex; gap: 20px; z-index: 100; opacity: 0.9; }
			.kbd-pill { background: #495057; padding: 1px 5px; border-radius: 3px; font-family: monospace; border: 1px solid #6c757d; }
			
			.total-row td { padding: 8px 12px; border: 1px solid #ccc; font-weight: 700; }
		`;
		if (!$('#ledger-review-styles').length) {
			$('<style id="ledger-review-styles">').html(css).appendTo('head');
		}
	}

	async load_data() {
		frappe.dom.freeze(__('Loading Ledger...'));
		try {
			const r = await frappe.db.get_doc('Nakoda Ledger Day', this.dashboard_id);
			this.ledger_day = r;
			this.rows = r.ledger_rows || [];
		} finally {
			frappe.dom.unfreeze();
		}
	}

	render() {
		const jama_rows = this.rows.filter(r => r.transaction_type === 'जमा');
		const udhaari_rows = this.rows.filter(r => r.transaction_type === 'उधारी');

		const total_records = this.rows.length;
		const matched_jama = jama_rows.filter(r => !!r.customer).length;
		const unmatched_jama = jama_rows.length - matched_jama;
		const matched_udhaari = udhaari_rows.filter(r => !!r.customer).length;
		const unmatched_udhaari = udhaari_rows.length - matched_udhaari;

		this.page.main.html(`
			<div class="ledger-review-container">
				<div class="review-header">
					<div class="header-main">Extraction Completed for ${frappe.datetime.str_to_user(this.ledger_day.ledger_date)}</div>
					<div class="header-sub">
                        Total: ${total_records} records &nbsp;|&nbsp; 
                        जमा: ${jama_rows.length} (${matched_jama} mapped, ${unmatched_jama} unmatched) &nbsp;|&nbsp; 
                        उधारी: ${udhaari_rows.length} (${matched_udhaari} mapped, ${unmatched_udhaari} unmatched)
                    </div>
				</div>

				<div class="section-title" style="color: green;">📊 ${__('जमा (Jama) Transactions')}</div>
				${this.render_table(jama_rows, 'jama')}

				<div class="section-title" style="color: red;">📉 ${__('उधारी (Udhaari) Transactions')}</div>
				${this.render_table(udhaari_rows, 'udhaari')}
				
				<div style="height: 100px;"></div>
			</div>
			<div class="footer-help">
				<span><span class="kbd-pill">↑</span> <span class="kbd-pill">↓</span> Navigate</span>
				<span><span class="kbd-pill">Enter</span> Next</span>
				<span><span class="kbd-pill">Space</span> Change Customer</span>
                <span><span class="kbd-pill">Del</span> Remove Row</span>
				<span><span class="kbd-pill">Esc</span> Cancel</span>
			</div>
		`);

		this.page.clear_primary_action();
		this.page.set_primary_action(__('Post Ledger Entries'), () => {
			frappe.confirm(__('Post all pending entries to ERPNext?'), () => {
				frappe.call({
					method: 'nakoda_automation.ledger_sync.api.post_ledger_entries',
					args: { dashboard_id: this.dashboard_id },
					callback: (r) => {
						if (r.message && r.message.status === 'success') {
							frappe.show_alert({ message: __('Posted Successfully'), indicator: 'green' });
							frappe.set_route('List', 'Nakoda Ledger Day');
						} else if (r.message && r.message.status === 'error') {
							frappe.msgprint(r.message.message);
						}
					}
				});
			});
		});

		this.page.set_secondary_action(__('Add New Customer'), () => {
			this.select_row_for_new_customer();
		});

		this.attach_events();
		this.sync_focus();
	}

	render_table(rows, id) {
		if (!rows.length) return `<div class="text-muted" style="font-size: 0.88rem; margin-left: 10px;">No records</div>`;

		let html = `
            <div style="overflow-x:auto; width:100%;">
                <table class="review-table" id="table-${id}">
                    <thead>
                        <tr>
                            <th width="40">#</th>
                            <th width="180">Raw Name</th>
                            <th width="120">Raw Village</th>
                            <th width="140">Village</th>
                            <th>Matched Customer</th>
                            <th width="120">Via</th>
                            <th width="80" class="text-center">Score</th>
                             <th width="120" class="text-right">Amount</th>
                            <th width="30"></th>
                        </tr>
                    </thead>
                    <tbody>
		`;

		let total_amt = 0;
		rows.forEach((r, idx) => {
			const md = JSON.parse(r.match_info || '{}');
			const score = parseFloat(md.best_score || md.score || 0);
			const score_class = score >= 70 ? 'score-high' : (score >= 40 ? 'score-medium' : 'score-low');
			const matched = !!r.customer;
			const is_corrected = md.corrected;

			const m_vil = md.matched_village || "";
			const r_vil = r.village || "";
			let vil_html = '—';
			if (matched && m_vil) vil_html = `<span class="vil-match">✔ ${m_vil}</span>`;
			else if (r_vil) vil_html = `<span class="vil-mismatch">✘ ${r_vil}</span>`;

			total_amt += flt(r.amount);

			html += `
				<tr class="row-item ${is_corrected ? 'corrected' : ''}" data-idx="${r.idx - 1}" data-row-id="${r.name}">
					<td style="color: #555;">${idx + 1}</td>
					<td>${r.customer_name_raw}</td>
					<td style="color: #666;">${r.village || '—'}</td>
					<td>${vil_html}</td>
					<td class="customer-cell">
						${matched ? `<b style="color:${score_class === 'score-high' ? 'green' : (score_class === 'score-medium' ? 'orange' : 'red')}">${r.customer}</b>` : '<span style="color:red;">✘ Not Matched</span>'}
					</td>
					<td style="color: #666; font-size: 11px;">${md.matched_via || (matched ? 'Manual' : 'No Match')}</td>
					<td class="text-center ${score_class}" style="font-weight: 700;">${score ? score.toFixed(1) + '%' : '—'}</td>
					<td class="text-right" style="font-weight: 600;">${format_currency(r.amount, 'INR', 0)}</td>
                    <td class="delete-cell" title="Delete row">×</td>
				</tr>
			`;
		});

		// Add Total Row
		html += `
			<tr class="total-row">
                <td colspan="7" style="text-align: right;">Total</td>
                <td style="text-align: right; color: ${id === 'jama' ? 'green' : 'red'};">${format_currency(total_amt, 'INR', 0)}</td>
                <td></td>
            </tr>
        `;

		html += `</tbody></table></div>`;
		return html;
	}

	attach_events() {
		const me = this;
		this.wrapper.find('.row-item').on('click', function (e) {
			const idx = $(this).data('idx');
			me.current_focus_index = idx;
			me.sync_focus();

			if ($(e.target).closest('.customer-cell').length) {
				me.open_customer_search(idx);
			} else if ($(e.target).closest('.delete-cell').length) {
				me.delete_row(idx);
			}
		});
	}

	sync_focus() {
		this.wrapper.find('.active-row').removeClass('active-row');
		const $target = this.wrapper.find(`.row-item[data-idx="${this.current_focus_index}"]`);
		if ($target.length) {
			$target.addClass('active-row');
			const el = $target[0];
			const rect = el.getBoundingClientRect();
			if (rect.top < 100 || rect.bottom > window.innerHeight - 50) {
				el.scrollIntoView({ behavior: 'smooth', block: 'center' });
			}
		}
	}

	setup_keyboard_nav() {
		$(document).off('keydown.ledger_review').on('keydown.ledger_review', (e) => {
			if ($('.modal:visible').length) return;

			if (e.key === 'ArrowDown') {
				e.preventDefault();
				if (this.current_focus_index < this.rows.length - 1) {
					this.current_focus_index++;
					this.sync_focus();
				}
			} else if (e.key === 'ArrowUp') {
				e.preventDefault();
				if (this.current_focus_index > 0) {
					this.current_focus_index--;
					this.sync_focus();
				}
			} else if (e.key === ' ') {
				e.preventDefault();
				this.open_customer_search(this.current_focus_index);
			} else if (e.key === 'Enter') {
				e.preventDefault();
				if (this.current_focus_index < this.rows.length - 1) {
					this.current_focus_index++;
					this.sync_focus();
				}
			} else if (e.key === 'Delete' || e.key === 'Backspace') {
				if (e.metaKey || e.ctrlKey) { // Require ctrl/meta + backspace to avoid accidental deletes
					this.delete_row(this.current_focus_index);
				}
			}
		});
	}

	open_customer_search(idx) {
		const row = this.rows[idx];
		const d = new frappe.ui.Dialog({
			title: __('Select Customer for {0}', [row.customer_name_raw]),
			fields: [
				{
					label: 'Customer',
					fieldname: 'customer',
					fieldtype: 'Link',
					options: 'Customer',
					reqd: 1,
					get_query: () => {
						return {
							filters: { disabled: 0 }
						}
					}
				}
			],
			primary_action_label: __('Update'),
			primary_action: (values) => {
				this.update_row_customer(idx, values.customer);
				d.hide();
			}
		});
		d.show();
	}

	open_add_customer_dialog(idx) {
		const row = this.rows[idx];
		const d = new frappe.ui.Dialog({
			title: __('Add New Customer'),
			fields: [
				{
					label: 'Customer Name',
					fieldname: 'customer_name',
					fieldtype: 'Data',
					default: row.customer_name_raw,
					reqd: 1
				},
				{
					label: 'Village',
					fieldname: 'village',
					fieldtype: 'Link',
					options: 'Village',
					default: row.village || ''
				},
				{
					label: 'Mobile No.',
					fieldname: 'mobile_no',
					fieldtype: 'Data'
				},
				{
					label: 'Reference',
					fieldname: 'reference',
					fieldtype: 'Data'
				},
				{
					label: 'Pata (Local Address)',
					fieldname: 'pata',
					fieldtype: 'Small Text'
				}
			],
			primary_action_label: __('Add'),
			primary_action: (values) => {
				frappe.call({
					method: 'nakoda_automation.ledger_sync.api.add_new_customer',
					args: values,
					callback: (r) => {
						if (r.message && r.message.status === 'success') {
							const customer_id = r.message.customer_id;
							this.update_row_customer(idx, customer_id);
							d.hide();
						} else if (r.message && r.message.status === 'error') {
							frappe.msgprint(r.message.message);
						}
					}
				});
			}
		});
		d.show();
	}

	select_row_for_new_customer() {
		const options = this.rows
			.filter(r => !r.customer)
			.map(r => ({
				label: `#${r.idx}: ${r.customer_name_raw} (${r.village || 'No Village'}) - ${format_currency(r.amount, 'INR', 0)}`,
				value: r.idx - 1
			}));

		if (!options.length) {
			this.rows.forEach(r => {
				options.push({
					label: `#${r.idx}: ${r.customer_name_raw} (${r.village || 'No Village'}) - ${format_currency(r.amount, 'INR', 0)}`,
					value: r.idx - 1
				});
			});
		}

		const d = new frappe.ui.Dialog({
			title: __('Select Transaction for New Customer'),
			fields: [
				{
					label: 'Select Record',
					fieldname: 'row_idx',
					fieldtype: 'Select',
					options: options,
					reqd: 1,
					default: this.current_focus_index
				}
			],
			primary_action_label: __('Next'),
			primary_action: (values) => {
				d.hide();
				this.open_add_customer_dialog(parseInt(values.row_idx));
			}
		});
		d.show();
	}

	update_row_customer(idx, customer_id) {
		frappe.call({
			method: 'nakoda_automation.ledger_sync.api.update_customer_mapping',
			args: {
				dashboard_id: this.dashboard_id,
				row_index: idx,
				customer_id: customer_id
			},
			callback: (r) => {
				if (r.message && r.message.status === 'success') {
					const row = this.rows[idx];
					row.customer = r.message.customer_name || r.message.customer_id;
					let md = JSON.parse(row.match_info || '{}');
					md.corrected = true;
					md.best_score = 100;
					md.matched_via = 'Manual';
					row.match_info = JSON.stringify(md);
					this.refresh_row_ui(idx);
					frappe.show_alert({ message: __('Customer updated'), indicator: 'green' });
				}
			}
		});
	}

	delete_row(idx) {
		frappe.confirm(__('Remove this transaction row from the summary?'), () => {
			frappe.call({
				method: 'nakoda_automation.ledger_sync.api.delete_ledger_row',
				args: {
					dashboard_id: this.dashboard_id,
					row_index: idx
				},
				callback: (r) => {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({ message: __('Row removed'), indicator: 'blue' });
						this.init(); // Full refresh to re-index rows and update totals
					} else if (r.message && r.message.status === 'error') {
						frappe.msgprint(r.message.message);
					}
				}
			});
		});
	}

	refresh_row_ui(idx) {
		const row = this.rows[idx];
		const $row = this.wrapper.find(`.row-item[data-idx="${idx}"]`);
		$row.addClass('corrected');
		$row.find('.customer-cell').html(`<b style="color:green">${row.customer}</b>`);
		$row.find('.score-low, .score-medium, .score-high')
			.removeClass('score-low score-medium')
			.addClass('score-high')
			.text('100.0%');
		$row.find('td:nth-child(6)').text('Manual');
	}
}
