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

		// Switch UI on resize (Device Mode toggle)
		$(window).off('resize.ledger_review').on('resize.ledger_review', () => {
			if (this.last_width !== window.innerWidth) {
				this.last_width = window.innerWidth;
				this.render();
			}
		});
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
			
			.edit-input { width: 100%; border: 1px solid #ddd; padding: 2px 5px; border-radius: 3px; font-size: 0.85rem; }
			.edit-input:focus { border-color: #4a90e2; outline: none; box-shadow: 0 0 0 2px rgba(74,144,226,0.2); }
			.tenure-flex { display: flex; gap: 4px; align-items: center; }
			.unit-select { width: 75px; background: #fff; }
			
			/* Mobile Styles */
			.mobile-review-shell { display: flex; flex-direction: column; background: #fafafa; margin: -15px; min-height: calc(100vh - 60px); }
			.mobile-header { position: sticky; top: 0; display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-bottom: 1px solid rgba(0,0,0,0.1); font-weight: bold; font-size: 1.1rem; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
			.m-type { border-radius: 4px; padding: 4px 10px; font-size: 0.95rem; }
			.m-type.jama { background: #e6f4ea; color: #1e8e3e; }
			.m-type.udhaari { background: #fce8e6; color: #d93025; }
			.mobile-card { flex: 1; overflow-y: auto; padding: 15px; padding-bottom: 20px; }
			.m-card-section { background: #fff; border-radius: 12px; padding: 18px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
			.m-title { font-size: 0.85rem; text-transform: uppercase; color: #888; margin-bottom: 10px; letter-spacing: 0.5px; font-weight: 600; }
			.m-data { font-size: 1.15rem; color: #222; word-wrap: break-word; line-height: 1.4; }
			.m-data.truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
			
			.mobile-actions { position: sticky; bottom: 85px; padding: 12px 15px; background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-top: 1px solid rgba(0,0,0,0.1); display: flex; gap: 12px; z-index: 10; margin-top: auto; }
			.m-btn { flex: 1; height: 48px; border-radius: 8px; font-size: 1.05rem; font-weight: bold; border: none; cursor: pointer; }
			.m-btn-primary { background: #4a90e2; color: #fff; }
			.m-btn-secondary { background: #fff; color: #333; border: 1px solid #ccc; }
			
			.mobile-nav { display: none; position: sticky; bottom: 0; padding: 10px 15px 20px 15px; background: #fff; border-top: 1px solid #eee; justify-content: space-between; gap: 15px; z-index: 10;}
            @media (max-width: 768px) {
                .mobile-nav { display: flex; }
            }
			.m-nav-btn { flex: 1; height: 48px; border-radius: 8px; font-size: 1rem; background: #f8f9fa; border: 1px solid #ddd; font-weight: 600; color: #444; }
			.m-nav-btn:disabled { opacity: 0.5; }
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
		const isMobile = window.innerWidth < 768 || 'ontouchstart' in window;
		if (isMobile) {
			this.renderMobileUI();
		} else {
			this.renderDesktopUI();
		}
	}

	renderDesktopUI() {
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

	renderMobileUI() {
		this.page.clear_primary_action();
		this.page.clear_secondary_action();

		if (this.rows.length === 0) {
			this.page.main.html(`<div style="padding: 20px; text-align: center;">No records found</div>`);
			return;
		}

		this.page.main.html(`
			<div class="mobile-review-shell">
				<div class="mobile-header">
					<span class="m-index"></span>
					<span class="m-type"></span>
					<span class="m-amount"></span>
				</div>
				<div class="mobile-card" id="mobile-card-content">
					<!-- Content populated via js -->
				</div>
				<div class="mobile-actions">
					<button class="m-btn m-btn-secondary" id="m-btn-create">Create New</button>
					<button class="m-btn m-btn-primary" id="m-btn-change">Change Match</button>
				</div>
				<div class="mobile-nav">
					<button class="m-nav-btn" id="m-nav-prev">← Prev</button>
					<button class="m-nav-btn" id="m-nav-next">Next →</button>
				</div>
			</div>
		`);

		this.setup_mobile_events();
		this.updateMobileContent(this.current_focus_index);
	}

	updateMobileContent(idx) {
		const row = this.rows[idx];
		const md = JSON.parse(row.match_info || '{}');
		const score = parseFloat(md.best_score || md.score || 0);
		const score_class = score >= 70 ? 'score-high' : (score >= 40 ? 'score-medium' : 'score-low');
		const matched = !!row.customer;
		const is_corrected = md.corrected;

		const m_vil = md.matched_village || "";
		const r_vil = row.village || "";
		let vil_html = '—';
		if (matched && m_vil) vil_html = `<span style="color: green;">✔ ${m_vil}</span>`;
		else if (r_vil) vil_html = `<span style="color: red;">✘ ${r_vil}</span>`;

		// Update Header
		$('.m-index').text(`[ ${idx + 1} / ${this.rows.length} ]`);
		$('.m-type').text(row.transaction_type).removeClass('jama udhaari').addClass(row.transaction_type === 'जमा' ? 'jama' : 'udhaari');
		$('.m-amount').text(format_currency(row.amount, 'INR', 0)).css('color', row.transaction_type === 'जमा' ? 'green' : 'red');

		// Update Card
		const display_name = md.corrected_customer_name || md.customer_name || row.customer;
		let match_display = `<div class="m-data truncate" style="color:${score_class === 'score-high' ? 'green' : (score_class === 'score-medium' ? 'orange' : 'red')}; font-weight: bold;">${display_name}</div>`;
		if (!matched) {
			match_display = `<div class="m-data text-danger" style="color:red; font-weight:bold;">✘ Not Matched</div>`;
		} else if (is_corrected) {
			match_display = `<div class="m-data text-primary" style="font-weight: bold; color: #4a90e2;">${display_name} <small style="color:#888;">(Manual)</small></div>`;
		}

		const html = `
			<div class="m-card-section">
				<div class="m-title">Excel Data</div>
				<div class="m-data truncate" style="font-weight: 500;">${row.customer_name_raw}</div>
				<div class="m-data" style="font-size: 0.95rem; color: #666; margin-top: 8px;">Village: <b>${row.village || '—'}</b></div>
				<div class="m-data" style="font-size: 0.95rem; color: #666; margin-top: 4px;">Reference: <b>${row.reference || '—'}</b></div>
			</div>

			<div class="m-card-section">
				<div class="m-title">Matched Customer</div>
				${match_display}
				<div class="m-data" style="font-size: 0.95rem; margin-top: 8px;">Village Match: ${vil_html}</div>
			</div>

			<div class="m-card-section">
				<div class="m-title">Customer Info</div>
				<div class="m-data" style="font-size: 0.95rem;">
					Mobile: <b>${row.mobile_no || '—'}</b>
				</div>
                ${row.transaction_type === 'उधारी' ? `
				<div class="m-data" style="font-size: 0.95rem; margin-top: 5px;">
					Tenure: <b>${row.tenure_value || '—'} ${row.tenure_unit || 'माह'}</b>
				</div>` : ''}
			</div>

			<div class="m-card-section">
				<div class="m-title">Match Info</div>
				<div class="m-data" style="font-size: 0.95rem;">
					Score: <span class="${score_class}">${score ? score.toFixed(1) + '%' : '—'}</span> <br>
					Via: <b>${md.matched_via || (matched ? 'Manual' : 'No Match')}</b>
				</div>
			</div>
		`;

		$('#mobile-card-content').html(html);

		// Update buttons state
		$('#m-nav-prev').prop('disabled', idx === 0);
		$('#m-nav-next').prop('disabled', idx === this.rows.length - 1);
		
		// Scroll to top
		$('.mobile-card').scrollTop(0);
	}

	setup_mobile_events() {
		const me = this;
		$('#m-btn-create').off('click').on('click', () => {
			me.open_add_customer_dialog(me.current_focus_index);
		});
		
		$('#m-btn-change').off('click').on('click', () => {
			me.open_customer_search(me.current_focus_index);
		});
		
		$('#m-nav-prev').off('click').on('click', () => {
			if (me.current_focus_index > 0) {
				me.current_focus_index--;
				me.updateMobileContent(me.current_focus_index);
			}
		});
		
		$('#m-nav-next').off('click').on('click', () => {
			if (me.current_focus_index < me.rows.length - 1) {
				me.current_focus_index++;
				me.updateMobileContent(me.current_focus_index);
			}
		});

		// Swipe Interactions
		let touchstartX = 0;
		let touchendX = 0;
		const slider = document.getElementById('mobile-card-content');
		if (!slider) return;

		slider.addEventListener('touchstart', e => {
			touchstartX = e.changedTouches[0].screenX;
		}, { passive: true });

		slider.addEventListener('touchend', e => {
			touchendX = e.changedTouches[0].screenX;
			handleGesture();
		}, { passive: true });

		function handleGesture() {
			if (touchendX < touchstartX - 50) {
				// Swipe Left -> Next
				$('#m-nav-next').click();
			}
			if (touchendX > touchstartX + 50) {
				// Swipe Right -> Prev
				$('#m-nav-prev').click();
			}
		}
	}

	render_table(rows, id) {
		if (!rows.length) return `<div class="text-muted" style="font-size: 0.88rem; margin-left: 10px;">No records</div>`;

		let html = `
            <div style="overflow-x:auto; width:100%;">
                <table class="review-table" id="table-${id}">
                    <thead>
                        <tr>
                            <th width="30">#</th>
                            <th width="120">Excel Name</th>
                            <th width="100">Excel Village</th>
                            <th width="130">Matched Customer</th>
                            <th width="90">Mobile</th>
                            ${id === 'udhaari' ? '<th width="85">Tenure</th>' : ''}
                            <th width="75">Via</th>
                            <th width="60" class="text-center">Score</th>
                            <th width="90" class="text-right">Amount</th>
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
			let vil_display = '';
			if (matched && m_vil) {
				vil_display = `<span class="vil-match">✔ ${r_vil || m_vil}</span>`;
			} else {
				// Show cross and whatever village name we have in Excel
				vil_display = `<span class="vil-mismatch">✘ ${r_vil || '—'}</span>`;
			}

			const display_name = md.corrected_customer_name || md.customer_name || r.customer;

			total_amt += flt(r.amount);

			html += `
				<tr class="row-item ${is_corrected ? 'corrected' : ''}" data-idx="${r.idx - 1}" data-row-id="${r.name}">
					<td style="color: #555;">${idx + 1}</td>
					<td style="white-space: normal; min-width: 100px;">${r.customer_name_raw}</td>
					<td style="font-size: 0.85rem;">${vil_display}</td>
					<td class="customer-cell" style="white-space: normal; min-width: 100px;">
						${matched ? `<b style="color:${score_class === 'score-high' ? 'green' : (score_class === 'score-medium' ? 'orange' : 'red')}">${display_name}</b>` : '<span style="color:red;">✘ Not Matched</span>'}
					</td>
                    <td>
                        <input type="text" class="edit-input row-mobile" value="${r.mobile_no || ''}" placeholder="Mobile">
                    </td>
                    ${id === 'udhaari' ? `
                    <td>
                        <div class="tenure-flex">
                            <input type="number" class="edit-input row-tenure-val" value="${r.tenure_value || ''}" style="width: 32px; padding: 2px;">
                            <select class="edit-input unit-select row-tenure-unit" style="width: 42px; padding: 2px; font-size: 11px;">
                                <option value="माह" ${r.tenure_unit === 'माह' ? 'selected' : ''}>M</option>
                                <option value="सप्ताह" ${r.tenure_unit === 'सप्ताह' ? 'selected' : ''}>W</option>
                                <option value="दिन" ${r.tenure_unit === 'दिन' ? 'selected' : ''}>D</option>
                            </select>
                        </div>
                    </td>` : ''}
                    <td style="color: #666; font-size: 11px;">
                        ${is_corrected ? 'Manual' : (md.v2_active ? 'V2-Pref' : (matched ? 'V1-Fuzzy' : 'None'))}
                    </td>
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
			const row_id = $(this).data('row-id');
			me.current_focus_index = idx;
			me.current_focus_row_id = row_id;
			me.sync_focus();

			if ($(e.target).closest('.customer-cell').length) {
				me.open_customer_search(idx, row_id);
			} else if ($(e.target).closest('.delete-cell').length) {
				me.delete_row(idx, row_id);
			}
		});

        this.wrapper.find('.row-mobile, .row-tenure-val, .row-tenure-unit').on('change', function() {
            const $tr = $(this).closest('.row-item');
            const row_id = $tr.data('row-id');
            const idx = $tr.data('idx');
            
            const mobile = $tr.find('.row-mobile').val();
            const t_val = $tr.find('.row-tenure-val').val() || null;
            const t_unit = $tr.find('.row-tenure-unit').val() || null;
            
            const row = me.rows.find(r => r.name === row_id);
            if (row) {
                me.update_row_customer(idx, row_id, row.customer, mobile, t_val, t_unit);
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

	open_customer_search(idx, row_id) {
		const row = this.rows.find(r => r.name === row_id) || this.rows[idx];
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
				this.update_row_customer(idx, row_id, values.customer);
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
							this.update_row_customer(idx, row.name, customer_id);
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

	update_row_customer(idx, row_id, customer_id, mobile_no=null, tenure_value=null, tenure_unit=null) {
        const row = this.rows.find(r => r.name === row_id) || this.rows[idx];
        
        // If not explicitly passed, pull from memory (for search dialog path)
        if (mobile_no === null) mobile_no = row.mobile_no;
        if (tenure_value === null) tenure_value = row.tenure_value;
        if (tenure_unit === null) tenure_unit = row.tenure_unit;

		frappe.call({
			method: 'nakoda_automation.ledger_sync.api.update_customer_mapping',
			args: {
				dashboard_id: this.dashboard_id,
				row_id: row_id,
				customer_id: customer_id,
                mobile_no: mobile_no,
                tenure_value: tenure_value,
                tenure_unit: tenure_unit
			},
			callback: (r) => {
				if (r.message && r.message.status === 'success') {
					const row = this.rows.find(r => r.name === row_id) || this.rows[idx];
					// It's critical to store the true doc ID back to the link field!
					row.customer = r.message.customer_id;
					if (r.message.village !== undefined) {
						row.village = r.message.village;
					}
                    row.mobile_no = r.message.mobile_no || mobile_no;
                    row.tenure_value = r.message.tenure_value !== undefined ? r.message.tenure_value : tenure_value;
                    row.tenure_unit = r.message.tenure_unit || tenure_unit;
					
					let md = JSON.parse(row.match_info || '{}');
					md.corrected = true;
					md.best_score = 100;
					md.matched_via = 'Manual';
					md.corrected_customer_name = r.message.customer_name;
					row.match_info = JSON.stringify(md);
					
					this.refresh_row_ui(idx, row_id);
					frappe.show_alert({ message: __('Customer updated'), indicator: 'green' });
				}
			}
		});
	}

	delete_row(idx, row_id) {
		frappe.confirm(__('Remove this transaction row from the summary?'), () => {
			frappe.call({
				method: 'nakoda_automation.ledger_sync.api.delete_ledger_row',
				args: {
					dashboard_id: this.dashboard_id,
					row_id: row_id
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

	refresh_row_ui(idx, row_id) {
		const isMobile = window.innerWidth < 768 || 'ontouchstart' in window;
		if (isMobile) {
			this.updateMobileContent(idx);
			return;
		}

		const row = this.rows.find(r => r.name === row_id) || this.rows[idx];
		const md = JSON.parse(row.match_info || '{}');
		const display_name = md.corrected_customer_name || md.customer_name || row.customer;
		const $row = this.wrapper.find(`.row-item[data-row-id="${row_id}"]`);
		$row.addClass('corrected');
		$row.find('.customer-cell').html(`<b style="color:green">${display_name}</b>`);
		$row.find('.score-low, .score-medium, .score-high')
			.removeClass('score-low score-medium')
			.addClass('score-high')
			.text('100.0%');
        
        // Update Matched Via text (column depends on if tenure exists)
        const matched_via_cell = row.transaction_type === "उधारी" ? 'td:nth-child(7)' : 'td:nth-child(6)';
		$row.find(matched_via_cell).text('Manual');
	}
}
