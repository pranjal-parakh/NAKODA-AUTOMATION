frappe.pages['customer_profile'].on_page_load = function (wrapper) {
    if (typeof Chart === 'undefined') {
        frappe.require('https://cdn.jsdelivr.net/npm/chart.js', () => {
            setup_profile_page(wrapper);
        });
    } else {
        setup_profile_page(wrapper);
    }
}

function setup_profile_page(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Customer Intelligence',
        single_column: true
    });

    // Add 'View ERP Form' back-link
    page.add_inner_button('View ERP Form', () => {
        const customer_name = frappe.get_route()[1] || frappe.route_options.name;
        if (customer_name) {
            frappe.set_route('Form', 'Customer', customer_name);
        } else {
            frappe.msgprint('Customer name not found.');
        }
    });

    // Re-inject glassmorphism css (or we could move to global)
    const css = `
		.profile-body { padding: 20px; background: #f8f9fc; min-height: 90vh; color: #1a1c21; }
        .glass-card-dark {
			background: white;
            border: 1px solid #e2e8f0;
			border-radius: 16px;
			padding: 24px;
			box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            margin-bottom: 24px;
		}

        .profile-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .cust-name { font-size: 1.8rem; font-weight: 800; color: #1a202c; }
        .cust-meta { color: #718096; font-size: 0.9rem; margin-top: 4px; }

        .stat-box { text-align: center; padding: 15px; border-right: 1px solid #edf2f7; }
        .stat-box:last-child { border-right: none; }
        .stat-label { font-size: 0.75rem; color: #a0aec0; text-transform: uppercase; font-weight: 700; }
        .stat-val { font-size: 1.4rem; font-weight: 700; color: #2d3748; margin-top: 5px; }

        .timeline-container { position: relative; padding-left: 30px; border-left: 2px solid #e2e8f0; margin-left: 10px; }
        .timeline-item { position: relative; margin-bottom: 12px; }
        .timeline-item::before {
            content: ""; position: absolute; left: -39px; top: 6px; width: 12px; height: 12px; 
            border-radius: 50%; border: 3px solid white; box-shadow: 0 0 0 2px #e2e8f0;
        }
        .item-udhaari::before { background: #e53e3e; }
        .item-jama::before { background: #38a169; }

        .timeline-date { font-size: 0.7rem; color: #a0aec0; font-weight: 600; margin-bottom: 2px; }
        .timeline-content {
            background: #fff; padding: 8px 14px; border-radius: 12px; border: 1px solid #e2e8f0;
            display: flex; justify-content: space-between; align-items: center;
        }

        .overdue-low { border-left: 5px solid #ecc94b !important; }
        .overdue-mid { border-left: 5px solid #ed8936 !important; }
        .overdue-high { border-left: 5px solid #e53e3e !important; }
	`;

    $('<style>').prop('type', 'text/css').html(css).appendTo('head');

    wrapper.profile = new CustomerProfile(wrapper, page);
}

class CustomerProfile {
    constructor(wrapper, page) {
        this.wrapper = $(wrapper).find('.layout-main-section');
        this.page = page;
        this.customer_name = frappe.get_route()[1] || frappe.route_options.name;

        if (!this.customer_name) {
            this.wrapper.html('<div class="p-5 text-center">Please select a customer via Dashboard.</div>');
            return;
        }

        this.timelineLimit = 4;
        this.invoiceLimit = 2;
        this.fullLedger = [];
        this.fullInvoices = [];
        this.init();
    }

    init() {
        this.render_skeleton();
        this.fetch_all();
    }

    render_skeleton() {
        this.wrapper.html(`
			<div class="profile-body">
                <!-- Header -->
				<div class="glass-card-dark">
                    <div class="profile-header">
                        <div>
                            <div class="cust-name" id="p-name">Loading...</div>
                            <div class="cust-meta" id="p-ref-addr" style="font-size: 0.9rem; margin-top: 4px; color: #4a5568; display: none;"></div>
                            <div class="cust-meta" id="p-meta" style="font-size: 0.9rem; margin-top: 4px; color: #4a5568;">Village | Phone</div>
                        </div>
                        <div class="d-flex">
                            <div class="stat-box"><div class="stat-label">Borrowed</div><div class="stat-val" id="s-borrowed">₹ 0</div></div>
                            <div class="stat-box"><div class="stat-label">Repaid</div><div class="stat-val" id="s-repaid">₹ 0</div></div>
                            <div class="stat-box"><div class="stat-label">Outstanding</div><div class="stat-val" id="s-outstanding" style="color: #e53e3e">₹ 0</div></div>
                        </div>
                    </div>
				</div>

                <div class="row">
                    <!-- Left: Main Section -->
                    <div class="col-md-7">
                        <div class="glass-card-dark" style="margin-bottom: 20px;">
                            <div class="stat-label" style="margin-bottom: 20px;">Active Invoices</div>
                            <div id="invoice-list"></div>
                            <div id="invoice-actions" class="text-center mt-2"></div>
                        </div>

                        <div class="glass-card-dark">
                            <div class="stat-label" style="margin-bottom: 20px;">Repayment Timeline</div>
                            <div class="timeline-container" id="timeline-list">
                                <!-- entries -->
                            </div>
                            <div id="timeline-actions" class="text-center mt-3"></div>
                        </div>
                    </div>

                    <!-- Right: Analysis Section -->
                    <div class="col-md-5">
                        <div class="glass-card-dark">
                            <div class="stat-label" style="margin-bottom: 10px;">Transaction Ledger</div>
                            <div class="" style="overflow-x: auto;">
                                <table class="table table-sm" style="font-size: 0.75rem; margin-top: 10px; color: #4a5568;" id="ledger-table">
                                    <thead>
                                        <tr style="background: #f7fafc;">
                                            <th>दिनांक</th>
                                            <th>जमा (+)</th>
                                            <th>उधार (-)</th>
                                            <th>बकाया</th>
                                        </tr>
                                    </thead>
                                    <tbody></tbody>
                                </table>
                            </div>

                            <div class="stat-label" style="margin-top: 25px; margin-bottom: 15px;">Pattern Trend</div>
                            <div style="height: 200px;"><canvas id="repaymentChart"></canvas></div>
                        </div>
                    </div>
                </div>
			</div>
		`);
    }

    fetch_all() {
        // 1. Meta & Metrics
        frappe.call({
            method: 'nakoda_automation.dashboard.get_customer_profile',
            args: { customer_name: this.customer_name },
            callback: (r) => {
                const info = r.message.info;
                const m = r.message.metrics;
                this.page.set_title(info.customer_name);
                $('#p-name').text(info.customer_name);
                let refHtml = [];
                if (info.reference_name) {
                    refHtml.push(`रेफरेंस: <strong style="color: #1e293b;">${info.reference_name}</strong>`);
                }
                if (info.local_address) {
                    refHtml.push(`पता: <strong style="color: #1e293b;">${info.local_address}</strong>`);
                }
                if (refHtml.length > 0) {
                    $('#p-ref-addr').html(refHtml.join(' &nbsp;|&nbsp; ')).show();
                } else {
                    $('#p-ref-addr').hide();
                }

                const village_str = info.village ? `गाँव: <strong style="color: #1e293b;">${info.village}</strong>` : 'गाँव: -';
                const phone_str = info.phone ? `Phone No.: <strong style="color: #1e293b;">${info.phone}</strong>` : 'Phone No.: -';
                $('#p-meta').html(`${village_str} &nbsp;|&nbsp; ${phone_str}`);

                $('#s-borrowed').text(this.fmt(m.total_borrowed));
                $('#s-repaid').text(this.fmt(m.total_repaid));
                $('#s-outstanding').text(this.fmt(m.outstanding));
            }
        });

        // 2. Timeline
        frappe.call({
            method: 'nakoda_automation.dashboard.get_customer_ledger',
            args: { customer_name: this.customer_name },
            callback: (r) => {
                this.fullLedger = r.message || [];
                this.render_timeline_ui();
            }
        });

        // 3. Invoices
        frappe.call({
            method: 'nakoda_automation.dashboard.get_customer_invoices',
            args: { customer_name: this.customer_name },
            callback: (r) => {
                this.fullInvoices = (r.message || []).filter(inv => inv.outstanding_amount > 0);
                this.render_invoice_ui();
            }
        });
    }

    render_timeline_ui() {
        const list = $('#timeline-list');
        const actions = $('#timeline-actions');
        list.empty();
        actions.empty();

        // 1. Fill Ledger Table (Newest at top for table is usually preferred, but for consistent chronological view we can follow user preference)
        // User asked for "Oldest to Newest", so we'll append to list (Timeline) and prepend to table (Table)
        let runningBal = 0;
        const tableBody = $('#ledger-table tbody');
        tableBody.empty();

        this.fullLedger.forEach(item => {
            // Jama (+) adds to balance, Udhaari (-) subtracts (Debt is negative)
            runningBal += (item.type === 'Jama' ? item.amount : -item.amount);
            item.runningBalance = runningBal;

            const credit = item.type === 'Jama' ? `+ ₹ ${format_currency(item.amount)}` : '-';
            const debit = item.type === 'Udhaari' ? `- ₹ ${format_currency(item.amount)}` : '-';
            const creditColor = item.type === 'Jama' ? 'color: #38a169; font-weight: 700;' : 'opacity: 0.3;';
            const debitColor = item.type === 'Udhaari' ? 'color: #e53e3e; font-weight: 700;' : 'opacity: 0.3;';

            tableBody.prepend(`
                <tr>
                    <td>${frappe.datetime.str_to_user(item.posting_date)}</td>
                    <td style="${creditColor}">${credit}</td>
                    <td style="${debitColor}">${debit}</td>
                    <td style="font-weight: 800; color: #2d3748;">₹ ${format_currency(Math.abs(runningBal))}</td>
                </tr>
            `);

            // 2. Fill Timeline UI (Compact & chronological oldest to newest)
            const typeClass = item.type === 'Jama' ? 'item-jama' : 'item-udhaari';
            const typeLabel = item.type === 'Jama' ? 'जमा' : 'उधार';
            const amountColor = item.type === 'Jama' ? '#38a169' : '#e53e3e';
            const symbol = item.type === 'Jama' ? '+' : '-';

            list.append(`
                <div class="timeline-item ${typeClass}" style="margin-bottom: 8px;">
                    <div class="timeline-date" style="margin-bottom: 0;">${frappe.datetime.str_to_user(item.posting_date)}</div>
                    <div class="timeline-content" style="padding: 6px 12px;">
                        <div style="flex: 1;">
                            <div style="font-weight: 700; font-size: 0.8rem;">
                                ${typeLabel} <span style="font-size: 0.65rem; font-weight: 400; opacity: 0.5;">#${item.id.split('-').pop()}</span>
                            </div>
                            <div style="font-size: 0.7rem; color: #718096">बकाया: ₹ ${format_currency(Math.abs(item.runningBalance))}</div>
                        </div>
                        <div style="font-size: 0.9rem; font-weight: 800; color: ${amountColor}">
                            ${symbol} ₹ ${format_currency(item.amount)}
                        </div>
                    </div>
                </div>
            `);
        });

        this.render_analytics(this.fullLedger);
    }

    render_invoice_ui() {
        const invList = $('#invoice-list');
        const actions = $('#invoice-actions');
        invList.empty();
        actions.empty();

        const total = this.fullInvoices.length;
        const toShow = this.fullInvoices.slice(0, this.invoiceLimit);

        toShow.forEach(inv => {
            const days = frappe.datetime.get_diff(frappe.datetime.nowdate(), inv.due_date);
            let overdueClass = '';
            if (days > 90) overdueClass = 'overdue-high';
            else if (days > 60) overdueClass = 'overdue-mid';
            else if (days > 30) overdueClass = 'overdue-low';

            invList.append(`
                <div class="timeline-content ${overdueClass}" style="margin-bottom: 10px; font-size: 0.85rem; cursor: pointer;" onclick="frappe.set_route('Form', 'Sales Invoice', '${inv.name}')">
                    <div>
                        <div style="font-weight: 700;">${inv.name}</div>
                        <div style="font-size: 0.7rem; color: #a0aec0">Due: ${frappe.datetime.str_to_user(inv.due_date)}</div>
                    </div>
                    <div class="text-right">
                        <div style="font-weight: 800; color: #e53e3e">₹ ${format_currency(inv.outstanding_amount)}</div>
                        <div style="font-size: 0.7rem; color: #cbd5e0">Total: ₹ ${format_currency(inv.grand_total)}</div>
                    </div>
                </div>
            `);
        });

        if (this.invoiceLimit < total) {
            const btn = $(`<button class="btn btn-default btn-xs w-100">Show All Invoices (${total})</button>`);
            btn.click(() => {
                this.invoiceLimit = total;
                this.render_invoice_ui();
            });
            actions.append(btn);
        }
    }

    render_analytics(ledger) {
        const sorted = ledger;
        const labels = sorted.map(i => frappe.datetime.str_to_user(i.posting_date));

        let balance = 0;
        const trend = sorted.map(i => {
            if (i.type === 'Jama') balance += i.amount;
            else balance -= i.amount;
            return balance;
        });

        new Chart(document.getElementById('repaymentChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Outstanding Trend',
                    data: trend,
                    borderColor: '#3182ce',
                    backgroundColor: 'rgba(49, 130, 206, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { grid: { color: '#f7fafc' } }
                }
            }
        });
    }

    fmt(val) {
        return '₹ ' + format_currency(val || 0, 'INR', 0);
    }
}
