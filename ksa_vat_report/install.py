import frappe


# Roles this app ships — may not exist yet on older sites
ZATCA_ROLES = [
    "ZATCA Configuration Manager",
    "ZATCA Accountant",
    "ZATCA Business Admin",
]

REPORT_NAME = "KSA VAT 201"


def after_install():
    _ensure_zatca_roles()
    _ensure_report_roles()
    frappe.db.commit()


def after_migrate():
    steps = [
        ("ensure_zatca_roles",  _ensure_zatca_roles),
        ("ensure_report_roles", _ensure_report_roles),
    ]
    for name, fn in steps:
        try:
            fn()
        except Exception:
            import traceback
            frappe.log_error(
                message=traceback.format_exc(),
                title=f"ksa_vat_report after_migrate: step '{name}' failed",
            )
    try:
        frappe.db.commit()
    except Exception:
        pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_zatca_roles():
    """
    Create each ZATCA role if it does not already exist in the database.
    Safe to run multiple times (idempotent).
    """
    for role_name in ZATCA_ROLES:
        if frappe.db.exists("Role", role_name):
            continue
        role = frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "desk_access": 1,
            "is_custom": 1,
        })
        role.insert(ignore_permissions=True)
        frappe.db.commit()


def _ensure_report_roles():
    """
    Add ZATCA roles to the KSA VAT 201 report's allowed-roles list.
    Skips any role that does not exist in the database yet, and skips
    roles that are already present — safe to run multiple times.
    """
    if not frappe.db.exists("Report", REPORT_NAME):
        return

    report = frappe.get_doc("Report", REPORT_NAME)
    existing = {row.role for row in report.roles}

    added = False
    for role_name in ZATCA_ROLES:
        if role_name in existing:
            continue
        if not frappe.db.exists("Role", role_name):
            # Role not created yet on this site — skip gracefully
            continue
        report.append("roles", {"role": role_name})
        added = True

    if added:
        report.save(ignore_permissions=True)
