"""
KSA VAT 201 — Saudi Arabia Quarterly VAT Return Report

Mirrors the official ZATCA VAT 201 form boxes:

  Section A  VAT on Sales and all other Outputs  (Box 1–4)
  Section B  VAT on Purchases and all other Inputs  (Box 5–9)
  Section C  Net VAT Due  (Box 10–16)

Classification logic:
  • Standard rated  — invoice has a tax row with rate > 0
  • Zero rated      — invoice has a tax row but rate = 0  (export / qualifying supply)
  • Exempt          — invoice has no tax rows at all

Credit notes (is_return = 1) are subtracted from their respective totals.

When "Show Details" is checked, every invoice is listed under its respective
VAT box with full audit trail (invoice #, date, party, net amount, VAT).
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    show_details = filters.get("show_details")
    columns = _get_columns(show_details)
    data = _get_data(filters, show_details)
    return columns, data


# ─── Columns ──────────────────────────────────────────────────────────────────

def _get_columns(show_details=False):
    cols = [
        {
            "label": _("Box"),
            "fieldname": "box",
            "fieldtype": "Data",
            "width": 60,
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 400,
        },
    ]

    if show_details:
        cols += [
            {
                "label": _("Invoice"),
                "fieldname": "invoice",
                "fieldtype": "Dynamic Link",
                "options": "invoice_type",
                "width": 180,
            },
            {
                "label": _("Invoice Type"),
                "fieldname": "invoice_type",
                "fieldtype": "Data",
                "width": 0,    # hidden helper column
                "hidden": 1,
            },
            {
                "label": _("Posting Date"),
                "fieldname": "posting_date",
                "fieldtype": "Date",
                "width": 110,
            },
            {
                "label": _("Party"),
                "fieldname": "party",
                "fieldtype": "Data",
                "width": 200,
            },
        ]

    cols += [
        {
            "label": _("Taxable Amount (SAR)"),
            "fieldname": "taxable_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 200,
        },
        {
            "label": _("VAT Amount (SAR)"),
            "fieldname": "vat_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 200,
        },
    ]

    return cols


# ─── Data ─────────────────────────────────────────────────────────────────────

def _get_data(filters, show_details=False):
    company   = filters.get("company")
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    sales     = _classify_invoices("Sales Invoice",    "Sales Taxes and Charges",    company, from_date, to_date)
    purchases = _classify_invoices("Purchase Invoice", "Purchase Taxes and Charges", company, from_date, to_date)

    # Section A totals
    a1_taxable = flt(sales["standard_taxable"])
    a1_vat     = flt(sales["standard_vat"])
    a2_taxable = flt(sales["zero_taxable"])
    a3_taxable = flt(sales["exempt_taxable"])
    a4_taxable = a1_taxable + a2_taxable + a3_taxable
    a4_vat     = a1_vat

    # Section B totals
    b5_taxable = flt(purchases["standard_taxable"])
    b5_vat     = flt(purchases["standard_vat"])
    b8_taxable = flt(purchases["exempt_taxable"])
    b9_taxable = b5_taxable + flt(purchases["zero_taxable"]) + b8_taxable
    b9_vat     = b5_vat

    # Section C — net VAT
    c10_vat = a1_vat
    c12_vat = c10_vat
    c13_vat = b5_vat
    c15_vat = c13_vat
    c16_vat = c12_vat - c15_vat

    label_c16 = (
        _("NET VAT DUE — Payable to ZATCA")
        if c16_vat >= 0
        else _("NET VAT REFUNDABLE from ZATCA")
    )

    rows = []

    # ── Section A ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION A: VAT ON SALES AND ALL OTHER OUTPUTS")))

    rows.append(_row("1", _("Standard rated sales (15% VAT)"), a1_taxable, a1_vat))
    if show_details:
        rows += _detail_rows(sales["standard_invoices"], "Sales Invoice")

    rows.append(_row("2", _("Zero rated sales (0% VAT — exports and qualifying supplies)"), a2_taxable, 0.0))
    if show_details:
        rows += _detail_rows(sales["zero_invoices"], "Sales Invoice")

    rows.append(_row("3", _("Exempt sales (no VAT applicable)"), a3_taxable, None))
    if show_details:
        rows += _detail_rows(sales["exempt_invoices"], "Sales Invoice")

    rows.append(_row("4", _("Total sales"), a4_taxable, a4_vat, bold=True))
    rows.append(_spacer())

    # ── Section B ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION B: VAT ON PURCHASES AND ALL OTHER INPUTS")))

    rows.append(_row("5", _("Standard rated domestic purchases (15% VAT)"), b5_taxable, b5_vat))
    if show_details:
        rows += _detail_rows(purchases["standard_invoices"], "Purchase Invoice")

    rows.append(_row("6", _("Imports subject to VAT (paid at customs)"), 0.0, 0.0))
    rows.append(_row("7", _("Imports subject to VAT — reverse charge mechanism"), 0.0, 0.0))

    rows.append(_row("8", _("Exempt purchases"), b8_taxable, None))
    if show_details:
        rows += _detail_rows(purchases["exempt_invoices"], "Purchase Invoice")

    rows.append(_row("9", _("Total purchases"), b9_taxable, b9_vat, bold=True))
    rows.append(_spacer())

    # ── Section C ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION C: NET VAT DUE")))
    rows.append(_row("10", _("Total VAT due (output VAT from Box 1)"),            None, c10_vat))
    rows.append(_row("11", _("Corrections from previous period"),                 None, 0.0))
    rows.append(_row("12", _("Total VAT due (Box 10 + Box 11)"),                  None, c12_vat, bold=True))
    rows.append(_row("13", _("Total eligible input VAT (Box 5 + Box 6 + Box 7)"), None, c13_vat))
    rows.append(_row("14", _("Corrections from previous period (input VAT)"),     None, 0.0))
    rows.append(_row("15", _("Total eligible input VAT (Box 13 + Box 14)"),       None, c15_vat, bold=True))
    rows.append(_row("16", label_c16,                                              None, c16_vat, bold=True))

    return rows


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _row(box, description, taxable_amount, vat_amount, bold=False):
    return {
        "box": box,
        "description": description,
        "invoice": None,
        "invoice_type": None,
        "posting_date": None,
        "party": None,
        "taxable_amount": taxable_amount,
        "vat_amount": vat_amount,
        "bold": 1 if bold else 0,
        "indent": 0,
    }


def _section(label):
    return {
        "box": "", "description": label,
        "invoice": None, "invoice_type": None, "posting_date": None, "party": None,
        "taxable_amount": None, "vat_amount": None,
        "bold": 1, "indent": 0,
    }


def _spacer():
    return {
        "box": "", "description": "",
        "invoice": None, "invoice_type": None, "posting_date": None, "party": None,
        "taxable_amount": None, "vat_amount": None,
        "bold": 0, "indent": 0,
    }


def _detail_rows(invoices, doctype):
    """Return indented detail rows for a list of classified invoices."""
    rows = []
    party_field = "customer_name" if doctype == "Sales Invoice" else "supplier_name"

    for inv in invoices:
        rows.append({
            "box": "",
            "description": _("Return") if inv.get("is_return") else "",
            "invoice": inv["name"],
            "invoice_type": doctype,
            "posting_date": inv["posting_date"],
            "party": inv.get(party_field, ""),
            "taxable_amount": flt(inv["base_net_total"]),
            "vat_amount": flt(inv["base_total_taxes_and_charges"]),
            "bold": 0,
            "indent": 1,
        })
    return rows


# ─── Invoice classification ───────────────────────────────────────────────────

def _classify_invoices(doctype, tax_child_table, company, from_date, to_date):
    """
    Fetch all submitted invoices for the company/period and classify them as:
      standard  — at least one tax row with rate > 0
      zero      — at least one tax row but all rates = 0
      exempt    — no tax rows at all

    Returns a dict with:
      standard_taxable, standard_vat, zero_taxable, exempt_taxable   (summary)
      standard_invoices, zero_invoices, exempt_invoices              (detail rows)
    """
    party_field = "customer_name" if doctype == "Sales Invoice" else "supplier_name"

    invoices = frappe.db.sql(
        f"""
        SELECT
            name,
            is_return,
            posting_date,
            {party_field},
            base_net_total,
            base_total_taxes_and_charges
        FROM
            `tab{doctype}`
        WHERE
            docstatus = 1
            AND company = %(company)s
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY
            posting_date, name
        """,
        {"company": company, "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    if not invoices:
        return {
            "standard_taxable": 0.0, "standard_vat": 0.0,
            "zero_taxable": 0.0, "exempt_taxable": 0.0,
            "standard_invoices": [], "zero_invoices": [], "exempt_invoices": [],
        }

    invoice_names = [d.name for d in invoices]

    # One query to get the max tax rate per invoice (tells us standard vs zero)
    tax_rows = frappe.db.sql(
        f"""
        SELECT
            parent,
            SUM(tax_amount_after_discount_amount) AS total_tax,
            MAX(rate)                              AS max_rate
        FROM
            `tab{tax_child_table}`
        WHERE
            parent IN %(names)s
            AND charge_type IN (
                'On Net Total',
                'On Previous Row Total',
                'On Previous Row Amount',
                'On Item Quantity'
            )
        GROUP BY
            parent
        """,
        {"names": invoice_names},
        as_dict=True,
    )

    tax_map = {row.parent: row for row in tax_rows}

    result = {
        "standard_taxable": 0.0,
        "standard_vat":     0.0,
        "zero_taxable":     0.0,
        "exempt_taxable":   0.0,
        "standard_invoices": [],
        "zero_invoices":     [],
        "exempt_invoices":   [],
    }

    for inv in invoices:
        # ERPNext already stores return (credit note) amounts as negative
        # in base_net_total and base_total_taxes_and_charges, so no manual
        # sign flip is needed — doing so would double-negate and inflate totals.
        net = flt(inv.base_net_total)
        tax = flt(inv.base_total_taxes_and_charges)
        row = tax_map.get(inv.name)

        if row:
            if flt(row.max_rate) > 0:
                result["standard_taxable"] += net
                result["standard_vat"]     += tax
                result["standard_invoices"].append(inv)
            else:
                result["zero_taxable"] += net
                result["zero_invoices"].append(inv)
        else:
            result["exempt_taxable"] += net
            result["exempt_invoices"].append(inv)

    return result
