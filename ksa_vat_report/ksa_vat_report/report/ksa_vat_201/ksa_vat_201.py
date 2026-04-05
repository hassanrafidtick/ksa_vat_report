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
VAT box with full audit trail columns:
  VAT Type, Date, Reference, Account/Customer/Supplier, Description,
  VAT Period, Exclusive, Inclusive, Tax, VAT Name
"""

import math
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
        {"label": _("Box"),         "fieldname": "box",         "fieldtype": "Data", "width": 60},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 360},
    ]

    if show_details:
        cols += [
            {"label": _("VAT Type"),    "fieldname": "vat_type",    "fieldtype": "Data",         "width": 130},
            {"label": _("Date"),        "fieldname": "posting_date","fieldtype": "Date",         "width": 100},
            {"label": _("Reference"),   "fieldname": "invoice",     "fieldtype": "Dynamic Link", "options": "invoice_type", "width": 160},
            {"label": _("Invoice Type"),"fieldname": "invoice_type","fieldtype": "Data",         "width": 0, "hidden": 1},
            {"label": _("Account"),     "fieldname": "party",       "fieldtype": "Data",         "width": 180},
            {"label": _("Description"), "fieldname": "doc_description", "fieldtype": "Data",     "width": 140},
            {"label": _("VAT Period"),  "fieldname": "vat_period",  "fieldtype": "Data",         "width": 90},
        ]

    cols += [
        {"label": _("Exclusive (SAR)"), "fieldname": "exclusive",  "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": _("Tax (SAR)"),       "fieldname": "tax",        "fieldtype": "Currency", "options": "currency", "width": 140},
    ]

    if show_details:
        cols += [
            {"label": _("Inclusive (SAR)"), "fieldname": "inclusive", "fieldtype": "Currency", "options": "currency", "width": 150},
            {"label": _("VAT Name"),        "fieldname": "vat_name", "fieldtype": "Data",     "width": 180},
        ]

    return cols


# ─── Quarter helper ───────────────────────────────────────────────────────────

def _quarter_label(posting_date):
    """Return 'Q1' … 'Q4' based on month."""
    if not posting_date:
        return ""
    month = posting_date.month if hasattr(posting_date, "month") else int(str(posting_date).split("-")[1])
    return "Q{}".format(math.ceil(month / 3))


# ─── Data ─────────────────────────────────────────────────────────────────────

def _get_data(filters, show_details=False):
    company   = filters.get("company")
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    sales     = _classify_invoices("Sales Invoice",    "Sales Taxes and Charges",    company, from_date, to_date)
    purchases = _classify_invoices("Purchase Invoice", "Purchase Taxes and Charges", company, from_date, to_date)

    # Section A totals
    a1_exclusive = flt(sales["standard_taxable"])
    a1_tax       = flt(sales["standard_vat"])
    a2_exclusive = flt(sales["zero_taxable"])
    a3_exclusive = flt(sales["exempt_taxable"])
    a4_exclusive = a1_exclusive + a2_exclusive + a3_exclusive
    a4_tax       = a1_tax

    # Section B totals
    b5_exclusive = flt(purchases["standard_taxable"])
    b5_tax       = flt(purchases["standard_vat"])
    b8_exclusive = flt(purchases["exempt_taxable"])
    b9_exclusive = b5_exclusive + flt(purchases["zero_taxable"]) + b8_exclusive
    b9_tax       = b5_tax

    # Section C — net VAT
    c10_tax = a1_tax
    c12_tax = c10_tax
    c13_tax = b5_tax
    c15_tax = c13_tax
    c16_tax = c12_tax - c15_tax

    label_c16 = (
        _("NET VAT DUE — Payable to ZATCA")
        if c16_tax >= 0
        else _("NET VAT REFUNDABLE from ZATCA")
    )

    rows = []

    # ── Section A ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION A: VAT ON SALES AND ALL OTHER OUTPUTS")))

    rows.append(_summary("1", _("Standard rated sales (15% VAT)"), a1_exclusive, a1_tax))
    if show_details:
        rows += _detail_rows(sales["standard_invoices"], "Sales Invoice", "Standard Rated")

    rows.append(_summary("2", _("Zero rated sales (0% VAT — exports and qualifying supplies)"), a2_exclusive, 0.0))
    if show_details:
        rows += _detail_rows(sales["zero_invoices"], "Sales Invoice", "Zero Rated")

    rows.append(_summary("3", _("Exempt sales (no VAT applicable)"), a3_exclusive, None))
    if show_details:
        rows += _detail_rows(sales["exempt_invoices"], "Sales Invoice", "Exempt")

    rows.append(_summary("4", _("Total sales"), a4_exclusive, a4_tax, bold=True))
    rows.append(_spacer())

    # ── Section B ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION B: VAT ON PURCHASES AND ALL OTHER INPUTS")))

    rows.append(_summary("5", _("Standard rated domestic purchases (15% VAT)"), b5_exclusive, b5_tax))
    if show_details:
        rows += _detail_rows(purchases["standard_invoices"], "Purchase Invoice", "Standard Rated")

    rows.append(_summary("6", _("Imports subject to VAT (paid at customs)"), 0.0, 0.0))
    rows.append(_summary("7", _("Imports subject to VAT — reverse charge mechanism"), 0.0, 0.0))

    rows.append(_summary("8", _("Exempt purchases"), b8_exclusive, None))
    if show_details:
        rows += _detail_rows(purchases["exempt_invoices"], "Purchase Invoice", "Exempt")

    rows.append(_summary("9", _("Total purchases"), b9_exclusive, b9_tax, bold=True))
    rows.append(_spacer())

    # ── Section C ─────────────────────────────────────────────────────────────
    rows.append(_section(_("SECTION C: NET VAT DUE")))
    rows.append(_summary("10", _("Total VAT due (output VAT from Box 1)"),            None, c10_tax))
    rows.append(_summary("11", _("Corrections from previous period"),                 None, 0.0))
    rows.append(_summary("12", _("Total VAT due (Box 10 + Box 11)"),                  None, c12_tax, bold=True))
    rows.append(_summary("13", _("Total eligible input VAT (Box 5 + Box 6 + Box 7)"), None, c13_tax))
    rows.append(_summary("14", _("Corrections from previous period (input VAT)"),     None, 0.0))
    rows.append(_summary("15", _("Total eligible input VAT (Box 13 + Box 14)"),       None, c15_tax, bold=True))
    rows.append(_summary("16", label_c16,                                              None, c16_tax, bold=True))

    return rows


# ─── Row builders ─────────────────────────────────────────────────────────────

_EMPTY_DETAIL = {
    "vat_type": None, "posting_date": None, "invoice": None,
    "invoice_type": None, "party": None, "doc_description": None,
    "vat_period": None, "inclusive": None, "vat_name": None,
}


def _summary(box, description, exclusive, tax, bold=False):
    row = {
        "box": box,
        "description": description,
        "exclusive": exclusive,
        "tax": tax,
        "bold": 1 if bold else 0,
        "indent": 0,
    }
    row.update(_EMPTY_DETAIL)
    return row


def _section(label):
    row = {"box": "", "description": label, "exclusive": None, "tax": None, "bold": 1, "indent": 0}
    row.update(_EMPTY_DETAIL)
    return row


def _spacer():
    row = {"box": "", "description": "", "exclusive": None, "tax": None, "bold": 0, "indent": 0}
    row.update(_EMPTY_DETAIL)
    return row


def _detail_rows(invoices, doctype, vat_type_label):
    """Return indented detail rows for a list of classified invoices."""
    rows = []
    party_field = "customer_name" if doctype == "Sales Invoice" else "supplier_name"

    for inv in invoices:
        is_return = flt(inv.get("is_return"))
        exclusive = flt(inv["base_net_total"])
        tax_amt   = flt(inv["base_total_taxes_and_charges"])
        inclusive  = exclusive + tax_amt

        if is_return:
            doc_desc = _("{} Return").format(
                _("Sales") if doctype == "Sales Invoice" else _("Purchase")
            )
        else:
            doc_desc = _("Sales Invoice") if doctype == "Sales Invoice" else _("Purchase Invoice")

        rows.append({
            "box": "",
            "description": "",
            "vat_type": _(vat_type_label),
            "posting_date": inv["posting_date"],
            "invoice": inv["name"],
            "invoice_type": doctype,
            "party": inv.get(party_field, ""),
            "doc_description": doc_desc,
            "vat_period": _quarter_label(inv["posting_date"]),
            "exclusive": exclusive,
            "tax": tax_amt,
            "inclusive": inclusive,
            "vat_name": inv.get("vat_name", ""),
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

    Each invoice dict also carries 'vat_name' — the description from the
    highest-rate tax row (e.g. "Standard Rate 15%").
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

    # Get max tax rate + the description of the tax row with the highest rate
    # per invoice.  We use a sub-query to pick the description belonging to
    # the row with MAX(rate).
    tax_rows = frappe.db.sql(
        f"""
        SELECT
            t.parent,
            SUM(t.tax_amount_after_discount_amount) AS total_tax,
            MAX(t.rate)                              AS max_rate,
            (
                SELECT t2.description
                FROM   `tab{tax_child_table}` t2
                WHERE  t2.parent = t.parent
                  AND  t2.charge_type IN (
                           'On Net Total',
                           'On Previous Row Total',
                           'On Previous Row Amount',
                           'On Item Quantity'
                       )
                ORDER BY t2.rate DESC
                LIMIT 1
            ) AS vat_name
        FROM
            `tab{tax_child_table}` t
        WHERE
            t.parent IN %(names)s
            AND t.charge_type IN (
                'On Net Total',
                'On Previous Row Total',
                'On Previous Row Amount',
                'On Item Quantity'
            )
        GROUP BY
            t.parent
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

        # Attach vat_name to the invoice dict for detail rows
        inv["vat_name"] = row.vat_name if row else ""

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
