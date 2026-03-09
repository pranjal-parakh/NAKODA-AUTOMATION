frappe.pages['ocr-test'].on_page_load = function (wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'OCR Verification (Surya)',
        single_column: true
    });

    $(frappe.render_template('ocr_test', {})).appendTo(page.main);

    let ocr_handler = new SuryaOCRHandler(wrapper);
    ocr_handler.init();
};

class SuryaOCRHandler {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.file_url = null;
    }

    init() {
        this.check_installation();
        this.setup_upload();
        this.bind_events();
    }

    check_installation() {
        frappe.call({
            method: 'nakoda_automation.ocr.surya_engine.check_surya_installed',
            callback: (r) => {
                const status_el = this.wrapper.find('#installation-status');
                if (r.message) {
                    status_el.text('Surya Installed: YES').removeClass('gray').addClass('green');
                } else {
                    status_el.text('Surya Installed: NO').removeClass('gray').addClass('red');
                }
            }
        });
    }

    setup_upload() {
        this.upload_field = frappe.ui.get_upload({
            parent: this.wrapper.find('#file-uploader'),
            args: {
                folder: 'Home/Attachments',
                is_private: 0
            },
            callback: (file) => {
                this.file_url = file.file_url;
                this.wrapper.find('#btn-run-ocr').prop('disabled', false);
                frappe.show_alert({
                    message: __('File uploaded successfully'),
                    indicator: 'green'
                });
                this.wrapper.find('#drop-zone').html(`
					<div class="text-success p-3">
						<i class="fa fa-check-circle fa-2x mb-2"></i>
						<p>Ready to process: <strong>${file.file_name}</strong></p>
					</div>
				`);
            }
        });
    }

    bind_events() {
        this.wrapper.find('#btn-run-ocr').on('click', () => {
            this.run_ocr();
        });
    }

    run_ocr() {
        if (!this.file_url) return;

        this.wrapper.find('#error-message').addClass('d-none');
        this.wrapper.find('#btn-run-ocr').prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-2"></i> Processing...');

        frappe.call({
            method: 'nakoda_automation.ocr.benchmark.run_surya_test',
            args: {
                file_url: this.file_url
            },
            callback: (r) => {
                this.wrapper.find('#btn-run-ocr').prop('disabled', false).html('<i class="fa fa-play mr-2"></i> Run Surya OCR');

                if (r.message && r.message.error) {
                    this.show_error(r.message.error);
                } else if (r.message) {
                    this.display_results(r.message);
                }
            },
            error: (err) => {
                this.wrapper.find('#btn-run-ocr').prop('disabled', false).html('<i class="fa fa-play mr-2"></i> Run Surya OCR');
                this.show_error('An unexpected server error occurred.');
            }
        });
    }

    display_results(data) {
        this.wrapper.find('#results-area').removeClass('d-none');
        this.wrapper.find('#raw-text-output').val(data.raw_text || '');
        this.wrapper.find('#json-block-output').text(JSON.stringify(data.blocks || [], null, 2));
        this.wrapper.find('#time-taken-badge').text(`Time: ${data.time_taken.toFixed(2)}s`);

        if (data.time_taken > 10) {
            this.wrapper.find('#time-taken-badge').removeClass('badge-info').addClass('badge-warning');
        } else {
            this.wrapper.find('#time-taken-badge').removeClass('badge-warning').addClass('badge-info');
        }

        // Scroll to results
        $('html, body').animate({
            scrollTop: this.wrapper.find('#results-area').offset().top - 100
        }, 500);
    }

    show_error(msg) {
        const err_el = this.wrapper.find('#error-message');
        err_el.text(msg).removeClass('d-none');
    }
}
