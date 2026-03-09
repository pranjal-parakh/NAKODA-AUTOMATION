frappe.pages['village_ledger'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Village Master Ledger',
        single_column: true
    });

    const css = `
		.village-body { padding: 20px; background: #fff; min-height: 90vh; }
        .v-header { background: #f8fafc; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 25px; }
        .v-stat { text-align: center; }
        .v-label { font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; }
        .v-val { font-size: 1.5rem; font-weight: 800; color: #1e293b; }
        .village-table { width: 100%; border-collapse: collapse; }
        .village-table th { padding: 12px; border-bottom: 2px solid #f1f5f9; text-align: left; color: #64748b; font-size: 0.85rem; }
        .village-table td { padding: 16px 12px; border-bottom: 1px solid #f1f5f9; }
        .village-table tr:hover { background: #f8fafc; cursor: pointer; }
	`;

    $('<style>').prop('type', 'text/css').html(css).appendTo('head');

    wrapper.village_ledger = new VillageLedger(wrapper, page);
}

class VillageLedger {
    constructor(wrapper, page) {
        this.wrapper = $(wrapper).find('.layout-main-section');
        this.page = page;
        this.init();
    }

    init() {
        this.render_skeleton();
        this.setup_filters();
    }

    render_skeleton() {
        this.wrapper.html(`
			<div class="village-body">
                <div class="v-header clearfix">
                    <div class="row">
                        <div class="col-md-4" id="v-filter-area"></div>
                        <div class="col-md-4 v-stat">
                            <div class="v-label">Total Exposure</div>
                            <div class="v-val" id="v-total-exposure">₹ 0</div>
                        </div>
                        <div class="col-md-4 v-stat">
                            <div class="v-label">Active Customers</div>
                            <div class="v-val" id="v-total-customers">0</div>
                        </div>
                    </div>
                </div>

                <div class="glass-card-dark" style="padding: 0;">
                    <table class="village-table" id="v-table">
                        <thead>
                            <tr>
                                <th>Customer</th>
                                <th>Outstanding</th>
                                <th>Total Borrowed</th>
                                <th>Last Payment</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr><td colspan="4" class="text-center p-5">Select a village to view ledger</td></tr>
                        </tbody>
                    </table>
                </div>
			</div>
		`);
    }

    setup_filters() {
        this.page.add_field({
            label: 'Select Village',
            fieldname: 'village',
            fieldtype: 'Link',
            options: 'Village',
            change: () => {
                const village = this.page.fields_dict.village.get_value();
                if (village) this.fetch_village_data(village);
            }
        });
    }

    fetch_village_data(village) {
        frappe.call({
            method: 'nakoda_automation.dashboard.get_village_ledger',
            args: { village: village },
            callback: (r) => {
                const d = r.message;
                $('#v-total-exposure').text('₹ ' + format_currency(d.summary.total_exposure));
                $('#v-total-customers').text(d.summary.total_customers);

                const tbody = $('#v-table tbody');
                tbody.empty();
                d.customers.forEach(c => {
                    const tr = $(`
                        <tr>
                            <td><b>${c.name}</b></td>
                            <td style="color: #e53e3e; font-weight: 700;">₹ ${format_currency(c.outstanding || 0)}</td>
                            <td>₹ ${format_currency(c.total_borrowed || 0)}</td>
                            <td style="opacity: 0.7;">${c.last_payment ? frappe.datetime.str_to_user(c.last_payment) : 'Never'}</td>
                        </tr>
                    `);
                    tr.click(() => frappe.set_route('customer_profile', c.name));
                    tbody.append(tr);
                });
            }
        });
    }
}
