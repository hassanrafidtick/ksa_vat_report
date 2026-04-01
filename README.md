# KSA VAT Report

A Frappe/ERPNext app that provides the **KSA VAT 201** report — the official Saudi VAT return form required by ZATCA.

## What is KSA VAT 201?

The VAT 201 is the quarterly VAT return that businesses in Saudi Arabia must file with ZATCA. It summarises:

- **Section A** — VAT on Sales (standard rated, zero rated, exempt)
- **Section B** — VAT on Purchases (domestic, imports, exempt)
- **Section C** — Net VAT due or claimable

## Installation

```bash
bench get-app https://github.com/your-org/ksa_vat_report.git
bench --site your-site.com install-app ksa_vat_report
bench --site your-site.com migrate
```

## Usage

Go to **Reports → KSA VAT Report → KSA VAT 201**

Filters:
- **Company** — select the company to run the return for
- **From Date / To Date** — the VAT period (typically a quarter)

## Compatibility

- Frappe v15 / v16
- ERPNext v15 / v16
- Works alongside `lavaloon-eg/ksa_compliance` (ZATCA Phase 2)

## License

MIT
