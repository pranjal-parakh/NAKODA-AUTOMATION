frappe.pages['ocr-test'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Hindi OCR Test',
        single_column: true
    });

    // Register template manually
    frappe.templates['ocr_test'] = `
        <div style="padding: 15px; font-family: monospace;">
            <div style="margin-bottom: 20px;">
                <input type="file" id="ocr-file-input" accept=".jpg, .jpeg, .png, .pdf">
                <button class="btn btn-primary" id="run-ocr-btn">Run Hindi OCR</button>
            </div>
            <div id="ocr-status" style="margin-bottom: 15px; font-weight: bold; color: blue;"></div>
            
            <div style="margin-bottom: 20px; background: #fafafa; padding: 15px; border-radius: 4px; border: 1px dashed #ccc;">
                <h4 style="margin-top: 0; font-weight: bold;">Diagnostics</h4>
                <div>Engine: <span id="ocr-engine">-</span></div>
                <div>Paddle Version: <span id="ocr-version">-</span> || Device: <span id="ocr-device">-</span></div>
                <div>Image Size: <span id="ocr-orig-size">-</span> &rarr; <span id="ocr-resize-size">-</span></div>
                <div>Execution Time: <span id="ocr-time" style="font-weight: bold; color: #d32f2f;">-</span> || Block Count: <span id="ocr-blocks">-</span></div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h4 style="font-weight: bold;">Raw Text</h4>
                <textarea id="ocr-raw-text" rows="15" style="width: 100%; font-family: monospace; padding: 10px;" readonly></textarea>
            </div>
            
            <div>
                <h4 style="font-weight: bold;">Raw JSON</h4>
                <pre id="ocr-raw-json" style="background: #f4f5f6; padding: 10px; max-height: 400px; overflow: auto; border: 1px solid #ccc;"></pre>
            </div>
        </div>
    `;

    $(frappe.render_template("ocr_test", {})).appendTo(page.main);

    // Bind events
    wrapper.find('#run-ocr-btn').on('click', function () {
        const fileInput = wrapper.find('#ocr-file-input')[0];
        if (!fileInput.files.length) {
            frappe.msgprint('Please select an image file first (.jpg, .jpeg, .png)');
            return;
        }

        const file = fileInput.files[0];
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['jpg', 'jpeg', 'png', 'pdf'].includes(ext)) {
            frappe.msgprint('Invalid file type');
            return;
        }

        const statusEl = wrapper.find('#ocr-status');
        const timeEl = wrapper.find('#ocr-time');
        const countEl = wrapper.find('#ocr-blocks');
        const versionEl = wrapper.find('#ocr-version');
        const deviceEl = wrapper.find('#ocr-device');
        const engineEl = wrapper.find('#ocr-engine');
        const origSizeEl = wrapper.find('#ocr-orig-size');
        const resizeSizeEl = wrapper.find('#ocr-resize-size');
        const textEl = wrapper.find('#ocr-raw-text');
        const jsonEl = wrapper.find('#ocr-raw-json');

        statusEl.text('Uploading image...').css('color', 'blue');
        timeEl.text('-');
        countEl.text('-');
        versionEl.text('-');
        deviceEl.text('-');
        engineEl.text('-');
        origSizeEl.text('-');
        resizeSizeEl.text('-');
        textEl.val('');
        jsonEl.text('');

        const fd = new FormData();
        fd.append('file', file, file.name);
        fd.append('is_private', 1);

        $.ajax({
            url: "/api/method/upload_file",
            data: fd,
            processData: false,
            contentType: false,
            type: "POST",
            headers: {
                "X-Frappe-CSRF-Token": frappe.csrf_token
            },
            success: function (r) {
                if (r.message && r.message.file_url) {
                    const file_url = r.message.file_url;
                    statusEl.text('Image uploaded. Running PaddleOCR...');

                    frappe.call({
                        method: 'nakoda_automation.ocr_test.api.test_hindi_ocr',
                        args: {
                            file_url: file_url
                        },
                        callback: function (ocr_r) {
                            if (ocr_r.exc) {
                                statusEl.text('OCR execution failed: server exception.').css('color', 'red');
                            } else {
                                let res = ocr_r.message;
                                if (res.error) {
                                    statusEl.text('Error: ' + res.error).css('color', 'red');
                                } else {
                                    statusEl.text('OCR Completed successfully.').css('color', 'green');
                                    timeEl.text(res.time_taken + ' s');
                                    countEl.text(res.block_count);
                                    versionEl.text(res.paddle_version || 'N/A');
                                    deviceEl.text(res.device || 'N/A');
                                    engineEl.text(res.engine || 'N/A');
                                    origSizeEl.text(res.image_original_size || 'N/A');
                                    resizeSizeEl.text(res.image_resized_size || 'N/A');
                                    textEl.val(res.raw_text);
                                    jsonEl.text(JSON.stringify(res.blocks, null, 2));
                                }
                            }
                        }
                    });
                } else {
                    statusEl.text('Upload succeeded but no file URL returned.').css('color', 'red');
                }
            },
            error: function (r) {
                statusEl.text('Upload failed.').css('color', 'red');
            }
        });
    });
};
