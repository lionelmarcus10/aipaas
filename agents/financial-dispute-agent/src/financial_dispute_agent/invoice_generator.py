"""Faker invoice generator — synthetic invoices with controlled anomalies.

Generates invoices that reference suppliers from CUAD, with controlled
variance, suspicious clauses, and confidence levels for testing.
"""

import random
from typing import Any

from faker import Faker
from pydantic import BaseModel, Field

faker = Faker()


class InvoiceLine(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    amount: float


class Invoice(BaseModel):
    invoice_id: str
    supplier_id: str
    supplier_name: str
    invoice_date: str
    due_date: str
    lines: list[InvoiceLine]
    total_amount: float
    expected_amount: float  # ce que le contrat dit
    variance_pct: float  # écart calculé
    metadata: dict[str, Any] = Field(default_factory=dict)


# Templates de clauses suspectes pour générer des anomalies
SUSPICIOUS_CLAUSES = [
    {"description": "Frais de gestion", "amount": 150, "reason": "non_contractuel"},
    {"description": "Frais de retard (22j)", "amount": 75, "reason": "retard_sous_30j"},
    {"description": "Majoration weekend", "amount": 200, "reason": "clause_floue"},
    {"description": "Supplément urgence", "amount": 300, "reason": "non_contractuel"},
    {"description": "Frais de traitement", "amount": 50, "reason": "non_contractuel"},
]

NORMAL_LINES = [
    {"description": "Service cloud 1 mois", "unit_price": 1500},
    {"description": "Licence logiciel annuelle", "unit_price": 3000},
    {"description": "Maintenance infrastructure", "unit_price": 800},
    {"description": "Consultation technique", "unit_price": 1200},
    {"description": "Hébergement serveur", "unit_price": 600},
    {"description": "Support premium 1 mois", "unit_price": 400},
    {"description": "Formation équipe", "unit_price": 2000},
    {"description": "Audit sécurité", "unit_price": 2500},
]


def generate_invoice(
    supplier_id: str,
    supplier_name: str,
    variance_pct: float = 0.0,
    add_suspicious: bool = False,
    confidence: float = 95.0,
) -> Invoice:
    """Generate one synthetic invoice with controlled parameters.

    Args:
        supplier_id: Supplier identifier (links to CUAD/MessyOps).
        supplier_name: Supplier name.
        variance_pct: Target variance percentage (0.0 = perfect match).
        add_suspicious: Add a suspicious non-contractual line.
        confidence: LLM confidence level to simulate (for test cases).
    """
    base_line = random.choice(NORMAL_LINES)
    expected = base_line["unit_price"]
    total = expected * (1 + variance_pct / 100)

    lines = [InvoiceLine(
        description=base_line["description"],
        unit_price=base_line["unit_price"],
        amount=base_line["unit_price"],
    )]

    if add_suspicious:
        clause = random.choice(SUSPICIOUS_CLAUSES)
        lines.append(InvoiceLine(
            description=clause["description"],
            unit_price=clause["amount"],
            amount=clause["amount"],
        ))
        total += clause["amount"]

    # Ajuster pour atteindre la variance cible
    if variance_pct > 0 and not add_suspicious:
        extra = total - expected
        lines.append(InvoiceLine(
            description="Ajustement tarifaire",
            unit_price=round(extra, 2),
            amount=round(extra, 2),
        ))

    return Invoice(
        invoice_id=f"INV-{faker.unique.numerify('####')}",
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        invoice_date=faker.date_between("-30d", "today").isoformat(),
        due_date=faker.date_between("today", "+30d").isoformat(),
        lines=lines,
        total_amount=round(total, 2),
        expected_amount=expected,
        variance_pct=round(variance_pct, 2),
        metadata={
            "confidence": confidence,
            "has_suspicious": add_suspicious,
        },
    )


def generate_test_invoices(suppliers: list[dict]) -> list[Invoice]:
    """Generate the 7 test cases from the validation matrix.

    Args:
        suppliers: List of {supplier_id, supplier_name, trust_score} dicts.

    Returns:
        7 invoices matching the test cases defined in sprint2-agents.md.
    """
    invoices = []

    # Cas 1 : écart 0%, confiance >95% → PAY
    s = suppliers[0]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 0, False, 98))

    # Cas 2 : écart 3%, confiance >80% → PARTIAL_PAY
    s = suppliers[0]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 3, False, 85))

    # Cas 3 : écart 15%, confiance >80%, trust 72% → DISPUTE + refund
    s = suppliers[1]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 15, True, 82))

    # Cas 4 : confiance <80% → HUMAN_REVIEW
    s = suppliers[0]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 5, True, 65))

    # Cas 5 : écart 20%, trust 30% → FREEZE + ESCALATE
    s = suppliers[2]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 20, True, 88))

    # Cas 6 : écart 8%, trust 85% → PARTIAL + NOTIFY
    s = suppliers[1]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 8, False, 90))

    # Cas 7 : écart 0%, confiance >95%, trust 90% → PAY + verify
    s = suppliers[1]
    invoices.append(generate_invoice(s["supplier_id"], s["supplier_name"], 0, False, 97))

    return invoices


def generate_random_invoices(suppliers: list[dict], n: int = 50) -> list[Invoice]:
    """Generate n random invoices for bulk testing.

    Args:
        suppliers: List of supplier dicts.
        n: Number of invoices to generate.
    """
    invoices = []
    for _ in range(n):
        s = random.choice(suppliers)
        variance = random.choice([0, 0, 0, 2, 5, 10, 15, 25])
        suspicious = variance > 5 and random.random() > 0.5
        confidence = random.uniform(60, 99) if suspicious else random.uniform(85, 99)
        invoices.append(generate_invoice(
            s["supplier_id"], s["supplier_name"], variance, suspicious, confidence
        ))
    return invoices
