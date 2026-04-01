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
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    return get_columns(), get_data(filters)


# ─── Columns ──────────────────────────────────────────────────────────────────

def get_columns():
    return [
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


# ─── Data ─────────────────────────────────────────────────────────────────────

def get_data(filters):
    company   = filters.get("company")
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    sales     = _classify_invoices("Sales Invoice",    "Sales Taxes and Charges",    company, from_date, to_date)
    purchases = _classify_invoices("Purchase Invoice", "Purchase Taxes and Charges", company, from_date, to_date)

    # Section A totals
    a1_taxable = flt(sales.get("standard_taxable", 0))
    a1_vat     = flt(sales.get("standard_vat", 0))
    a2_taxable = flt(sales.get("zero_taxable", 0))
    a3_taxable = flt(sales.get("exempt_taxable", 0))
    a4_taxable = a1_taxable + a2_taxable + a3_taxable
    a4_vat     = a1_vat

    # Section B totals
    b5_taxable = flt(purchases.get("standard_taxable", 0))
    b5_vat     = flt(purchases.get("standard_vat", 0))
    b8_taxable = flt(purchases.get("exempt_taxable", 0))
    b9_taxable = b5_taxable + flt(purchases.get("zero_taxable", 0)) + b8_taxable
    b9_vat     = b5_vat

    # Section C — net VAT
    c10_vat = a1_vat           # Output VAT
    c12_vat = c10_vat          # + corrections (box 11 = 0, manual entry in ZATCA portal)
    c13_vat = b5_vat           # Eligible input VAT
    c15_vat = c13_vat          # + corrections (box 14 = 0)
    c16_vat = c12_vat - c15_vat  # positive = payable, negative = refundable

    label_c16 = (
        _("NET VAT DUE — Payable to ZATCA")
        if c16_vat >= 0
        else _("NET VAT REFUNDABLE from ZATCA")
    )

    return [
        _section(_("SECTION A: VAT ON SALES AND ALL OTHER OUTPUTS")),
        _row("1",  _("Standard rated sales (15% VAT)"),                              a1_taxable, a1_vat),
        _row("2",  _("Zero rated sales (0% VAT — exports and qualifying supplies)"),  a2_taxable, 0.0),
        _row("3",  _("Exempt sales (no VAT applicable)"),                             a3_taxable, None),
        _row("4",  _("Total sales"),                                                  a4_taxable, a4_vat, bold=True),
        _spacer(),
        _section(_("SECTION B: VAT ON PURCHASES AND ALL OTHER INPUTS")),
        _row("5",  _("Standard rated domestic purchases (15% VAT)"),                 b5_taxable, b5_vat),
        _row("6",  _("Imports subject to VAT (paid at customs)"),                    0.0,        0.0),
        _row("7",  _("Imports subject to VAT — reverse charge mechanism"),           0.0,        0.0),
        _row("8",  _("Exempt purchases"),                                            b8_taxable, None),
        _row("9",  _("Total purchases"),                                             b9_taxable, b9_vat, bold=True),
        _spacer(),
        _section(_("SECTION C: NET VAT DUE")),
        _row("10", _("Total VAT due (output VAT from Box 1)"),                       None, c10_vat),
        _row("11", _("Corrections from previous period"),                            None, 0.0),
        _row("12", _("Total VAT due (Box 10 + Box 11)"),                             None, c12_vat, bold=True),
        _row("13", _("Total eligible input VAT (Box 5 + Box 6 + Box 7)"),           None, c13_vat),
        _row("14", _("Corrections from previous period (input VAT)"),               None, 0.0),
        _row("15", _("Total eligible input VAT (Box 13 + Box 14)"),                 None, c15_vat, bold=True),
        _row("16", label_c16,                                                        None, c16_vat, bold=True),
    ]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _row(box, description, taxable_amount, vat_amount, bold=False):
    return {
        "box": box,
        "description": description,
        "taxable_amount": taxable_amount,
        "vat_amount": vat_amount,
        "bold": 1 if bold else 0,
    }


def _section(label):
    return {"box": "", "description": label, "taxable_amount": None, "vat_amount": None, "bold": 1}


def _spacer():
    return {"box": "", "description": "", "taxable_amount": None, "vat_amount": None, "bold": 0}


# ─── Invoice classification ───────────────────────────────────────────────────

def _classify_invoices(doctype, tax_child_table, company, from_date, to_date):
    """
    Fetch all submitted invoices for the company/period and classify them as:
      standard  — at least one tax row with rate > 0
      zero      — at least one tax row but all rates = 0
      exempt    — no tax rows at all

    Returns a dict with keys:
      standard_taxable, standard_vat, zero_taxable, exempt_taxable
    """
    invoices = frappe.db.sql(
        f"""
        SELECT
            name,
            is_return,
            base_net_total,
            base_total_taxes_and_charges
        FROM
            `tab{doctype}`
        WHERE
            docstatus = 1
            AND company = %(company)s
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        """,
        {"company": company, "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    if not invoices:
        return {}

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
    }

    for inv in invoices:
        sign = -1 if flt(inv.is_return) else 1
        net  = flt(inv.base_net_total) * sign
        tax  = flt(inv.base_total_taxes_and_charges) * sign
        row  = tax_map.get(inv.name)

        if row:
            if flt(row.max_rate) > 0:
                # Standard rated — positive VAT rate applied
                result["standard_taxable"] += net
                result["standard_vat"]     += tax
            else:
                # Zero rated — tax template exists but rate = 0 (e.g. export)
                result["zero_taxable"] += net
        else:
            # Exempt — no tax rows whatsoever
            result["exempt_taxable"] += net

    return result
