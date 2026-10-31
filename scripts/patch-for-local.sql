UPDATE settings SET value = 'http://172.17.0.1:8000/' WHERE key = 'external_services.options_tracker_url';
UPDATE settings SET value = 'http://172.17.0.1:5000/' WHERE key = 'external_services.backtester_url';
UPDATE settings SET value = 'http://172.17.0.1:8001/' WHERE key = 'external_services.transaction_ocr_url';