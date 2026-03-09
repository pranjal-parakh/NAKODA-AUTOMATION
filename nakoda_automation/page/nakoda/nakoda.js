frappe.pages['nakoda'].on_page_load = function (wrapper) {
	// Ensure Chart.js is loaded
	if (typeof Chart === 'undefined') {
		frappe.require('https://cdn.jsdelivr.net/npm/chart.js', () => {
			setup_nakoda_page(wrapper);
		});
	} else {
		setup_nakoda_page(wrapper);
	}
}

function setup_nakoda_page(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Nakoda Control Center',
		single_column: true
	});

	// CSS Injector
	const css = `
		.nakoda-dashboard {
			padding: 20px;
			background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
			min-height: 90vh;
			border-radius: 12px;
			color: white !important;
			font-family: 'Inter', sans-serif;
		}

		.glass-card {
			backdrop-filter: blur(16px) saturate(180%);
			background: rgba(255, 255, 255, 0.1);
			border: 1px solid rgba(255, 255, 255, 0.2);
			border-radius: 16px;
			padding: 20px;
			box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
			transition: transform 0.3s ease, box-shadow 0.3s ease;
		}

		.glass-card:hover {
			transform: translateY(-5px);
			box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
			background: rgba(255, 255, 255, 0.15);
		}

		.metric-value {
			font-size: 2.2rem;
			font-weight: 800;
			margin: 10px 0;
			background: linear-gradient(to right, #fff, #ddd);
			-webkit-background-clip: text;
			-webkit-text-fill-color: transparent;
		}

		.metric-label {
			text-transform: uppercase;
			font-size: 0.75rem;
			letter-spacing: 1.5px;
			opacity: 0.8;
			font-weight: 600;
		}

		.chart-container {
			margin-top: 30px;
		}

		.dashboard-table {
			width: 100%;
			border-collapse: separate;
			border-spacing: 0 8px;
		}

		.dashboard-table th {
			text-align: left;
			padding: 12px;
			opacity: 0.6;
			font-size: 0.8rem;
		}

		.dashboard-table tr {
			background: rgba(255, 255, 255, 0.05);
			cursor: pointer;
			transition: 0.2s;
		}

		.dashboard-table tr:hover {
			background: rgba(255, 255, 255, 0.12);
		}

		.dashboard-table td {
			padding: 15px 12px;
		}

		.dashboard-table tr td:first-child { border-radius: 10px 0 0 10px; }
		.dashboard-table tr td:last-child { border-radius: 0 10px 10px 0; }

		.badge-jama { background: rgba(39, 174, 96, 0.2); color: #2ecc71; padding: 4px 10px; border-radius: 6px; }
		.badge-udhaari { background: rgba(231, 76, 60, 0.2); color: #e74c3c; padding: 4px 10px; border-radius: 6px; }

		.search-bar {
			background: rgba(255,255,255,0.1);
			border: 1px solid rgba(255,255,255,0.2);
			border-radius: 12px;
			color: white;
			padding: 10px 20px;
			width: 100%;
			margin-bottom: 20px;
			backdrop-filter: blur(5px);
		}
	`;

	$('<style>').prop('type', 'text/css').html(css).appendTo('head');

	wrapper.dashboard = new NakodaDashboard(wrapper, page);
}

class NakodaDashboard {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.page = page;
		this.init();
	}

	init() {
		this.render_layout();
		this.fetch_metrics();
		this.fetch_top_debtors();
		this.fetch_village_exposure();
		this.fetch_recent();
		this.setup_search();
	}

	render_layout() {
		this.wrapper.html(`
			<div class="nakoda-dashboard">
				<div class="row">
					<div class="col-md-5">
						<input type="text" class="search-bar" placeholder="🔍 Search Customer by Name, Village or Phone...">
					</div>
					<div class="col-md-7 text-right">
                        <button class="btn btn-default btn-sm btn-village" style="border-radius: 8px; margin-right: 5px;">📍 Village Ledger</button>
                        <button class="btn btn-default btn-sm btn-export" style="border-radius: 8px; margin-right: 5px;">📁 Export Outstanding</button>
						<button class="btn btn-primary btn-sm btn-upload" style="border-radius: 8px;">➕ Upload Ledger</button>
					</div>
				</div>

				<!-- Metrics Row -->
				<div class="row metrics-row">
					<div class="col-md-3">
						<div class="glass-card" id="metric-outstanding">
							<div class="metric-label">Total Outstanding</div>
							<div class="metric-value">₹ 0.0</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="glass-card" id="metric-udhaari">
							<div class="metric-label">Udhaari Today</div>
							<div class="metric-value">₹ 0.0</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="glass-card" id="metric-jama">
							<div class="metric-label">Jama Today</div>
							<div class="metric-value">₹ 0.0</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="glass-card" id="metric-overdue">
							<div class="metric-label">Total Overdue</div>
							<div class="metric-value" style="color: #ff4d4d !important;">₹ 0.0</div>
						</div>
					</div>
				</div>

				<!-- Charts Row -->
				<div class="row chart-container">
					<div class="col-md-6">
						<div class="glass-card" style="height: 400px;">
							<div class="metric-label">Village Wise Exposure</div>
							<div style="height: 320px;" id="village-chart-container">
								<canvas id="villageChart"></canvas>
							</div>
						</div>
					</div>
					<div class="col-md-6">
						<div class="glass-card" style="height: 400px;">
							<div class="metric-label">Top Debtors</div>
							<div style="height: 320px;" id="debtor-chart-container">
								<canvas id="debtorChart"></canvas>
							</div>
						</div>
					</div>
				</div>

				<!-- Recent Transactions -->
				<div class="row chart-container">
					<div class="col-md-12">
						<div class="glass-card">
							<div class="metric-label" style="margin-bottom: 15px;">Recent Transactions</div>
							<table class="dashboard-table" id="recent-table">
								<thead>
									<tr>
										<th>Date</th>
										<th>Customer</th>
										<th>Type</th>
										<th>Amount</th>
										<th>ID</th>
									</tr>
								</thead>
								<tbody>
									<tr><td colspan="5" class="text-center">Loading...</td></tr>
								</tbody>
							</table>
						</div>
					</div>
				</div>
			</div>
		`);

		this.wrapper.find('.btn-upload').click(() => {
			frappe.set_route('List', 'Nakoda Ledger Day');
		});

		this.wrapper.find('.btn-village').click(() => {
			frappe.set_route('village_ledger');
		});

		this.wrapper.find('.btn-export').click(() => {
			window.open('/api/method/nakoda_automation.dashboard.export_customer_outstanding');
		});
	}

	fetch_metrics() {
		frappe.call({
			method: 'nakoda_automation.dashboard.get_dashboard_metrics',
			callback: (r) => {
				const m = r.message;
				$('#metric-outstanding .metric-value').text(this.fmt(m.total_outstanding));
				$('#metric-udhaari .metric-value').text(this.fmt(m.today_udhaari));
				$('#metric-jama .metric-value').text(this.fmt(m.today_jama));
				$('#metric-overdue .metric-value').text(this.fmt(m.total_overdue));
			}
		});
	}

	fetch_village_exposure() {
		frappe.call({
			method: 'nakoda_automation.dashboard.get_village_exposure',
			callback: (r) => {
				const data = r.message;
				const labels = data.map(d => d.village || 'Undefined');
				const values = data.map(d => d.outstanding);

				new Chart(document.getElementById('villageChart'), {
					type: 'bar',
					data: {
						labels: labels,
						datasets: [{
							label: 'Outstanding ₹',
							data: values,
							backgroundColor: 'rgba(54, 162, 235, 0.6)',
							borderColor: 'rgba(54, 162, 235, 1)',
							borderWidth: 1,
							borderRadius: 8
						}]
					},
					options: {
						responsive: true,
						maintainAspectRatio: false,
						scales: {
							y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#fff' } },
							x: { grid: { display: false }, ticks: { color: '#fff' } }
						},
						plugins: { legend: { display: false } }
					}
				});
			}
		});
	}

	fetch_top_debtors() {
		frappe.call({
			method: 'nakoda_automation.dashboard.get_top_debtors',
			callback: (r) => {
				const data = r.message;
				const labels = data.map(d => d.name);
				const values = data.map(d => d.outstanding);

				new Chart(document.getElementById('debtorChart'), {
					type: 'doughnut',
					data: {
						labels: labels,
						datasets: [{
							data: values,
							backgroundColor: [
								'rgba(255, 99, 132, 0.7)',
								'rgba(54, 162, 235, 0.7)',
								'rgba(255, 206, 86, 0.7)',
								'rgba(75, 192, 192, 0.7)',
								'rgba(153, 102, 255, 0.7)'
							],
							borderWidth: 0
						}]
					},
					options: {
						responsive: true,
						maintainAspectRatio: false,
						plugins: {
							legend: { position: 'bottom', labels: { color: '#fff', padding: 20 } }
						}
					}
				});
			}
		});
	}

	fetch_recent() {
		frappe.call({
			method: 'nakoda_automation.dashboard.get_recent_transactions',
			callback: (r) => {
				const tbody = $('#recent-table tbody');
				tbody.empty();
				r.message.forEach(row => {
					const badge = row.type === 'Jama' ? 'badge-jama' : 'badge-udhaari';
					const tr = $(`
						<tr>
							<td>${frappe.datetime.str_to_user(row.posting_date)}</td>
							<td><b>${row.customer}</b></td>
							<td><span class="${badge}">${row.type}</span></td>
							<td>₹ ${format_currency(row.amount)}</td>
							<td style="opacity: 0.6; font-size: 0.8rem;">${row.name}</td>
						</tr>
					`);
					tr.click(() => frappe.set_route('customer_profile', row.customer));
					tbody.append(tr);
				});
			}
		});
	}

	setup_search() {
		const searchInput = $('.search-bar');
		searchInput.on('keypress', (e) => {
			if (e.which == 13) {
				const val = searchInput.val();
				if (!val) return;

				frappe.call({
					method: 'nakoda_automation.dashboard.search_customers',
					args: { query: val },
					callback: (r) => {
						if (r.message && r.message.length > 0) {
							// If exact match or first result
							frappe.set_route('customer_profile', r.message[0].name);
						} else {
							frappe.show_alert('No customer found.', 3);
						}
					}
				});
			}
		});
	}

	fmt(val) {
		return '₹ ' + format_currency(val || 0, 'INR', 0);
	}
}
