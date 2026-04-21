from . import __version__ as app_version

app_name = "ksa_vat_report"
app_title = "KSA VAT Report"
app_publisher = "Rafid Technology"
app_description = "KSA VAT 201 Report — Saudi quarterly VAT return for ERPNext"
app_email = "hasanm@rafidtech.com"
app_license = "MIT"
app_version = app_version

required_apps = ["frappe", "erpnext"]

# Install / migrate hooks
after_install = "ksa_vat_report.install.after_install"
after_migrate = "ksa_vat_report.install.after_migrate"

# Fixtures — exported via bench export-fixtures
fixtures = ["Role"]

# Jinja
jinja = {
    "methods": [
        "ksa_vat_report.jinja.money_in_words_ar",
        "ksa_vat_report.jinja.parse_json_safe",
    ]
}
