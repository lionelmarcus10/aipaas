"""Faker claim generator — synthetic FNOL declarations with controlled scenarios.

Generates insurance claims (First Notification of Loss) with controlled
complexity, fraud indicators, and expected triage outcomes for testing.

5 scenario categories:
  1. Simple (fast-track)     — minor damage, clear policy, low amount
  2. Complex (adjuster)      — moderate damage, active policy, needs assessment
  3. Fraud (SIU)             — recent policy, repeat claims, inflated amount
  4. Coverage exclusion      — claim type excluded by policy
  5. Missing info (request)  — incomplete claim data
"""

import random
from datetime import datetime, timedelta
from typing import Any

from faker import Faker
from pydantic import BaseModel, Field

faker = Faker()
faker.seed_instance(42)


# ─── Pydantic models ─────────────────────────────────────────────────

class FNOLClaim(BaseModel):
    """First Notification of Loss — the input the agent receives."""
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str                    # "auto_collision", "home_fire", "theft", "water_damage"
    incident_date: str
    claim_date: str
    claim_amount: float
    description: str                   # narrative of the incident
    police_report_filed: bool = False
    witnesses_count: int = 0
    expected_triage: str = ""          # ground truth for tests
    metadata: dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    """Insurance policy."""
    policy_id: str
    customer_id: str
    policy_type: str                   # "auto", "home", "health"
    coverage_type: str                 # "collision", "comprehensive", "liability"
    coverage_limit: float
    deductible: float
    premium_annual: float
    start_date: str
    end_date: str
    exclusions: list[str] = Field(default_factory=list)
    status: str = "active"             # "active", "expired", "cancelled"


class ClaimHistoryEntry(BaseModel):
    """A previous claim by a customer."""
    customer_id: str
    claim_id: str
    claim_date: str
    claim_type: str
    claim_amount: float
    fraud_found: bool = False


# ─── Scenario templates ──────────────────────────────────────────────

CLAIM_TYPES = ["auto_collision", "home_fire", "theft", "water_damage", "bodily_injury"]

POLICY_TYPES = {
    "auto_collision": {"policy_type": "auto", "coverage_type": "collision", "limit": 50000, "deductible": 500},
    "home_fire": {"policy_type": "home", "coverage_type": "comprehensive", "limit": 200000, "deductible": 1000},
    "theft": {"policy_type": "auto", "coverage_type": "comprehensive", "limit": 30000, "deductible": 250},
    "water_damage": {"policy_type": "home", "coverage_type": "comprehensive", "limit": 15000, "deductible": 500},
    "bodily_injury": {"policy_type": "auto", "coverage_type": "liability", "limit": 100000, "deductible": 0},
}

EXCLUSIONS = {
    "auto_collision": ["racing", "commercial_use", "intentional_damage"],
    "home_fire": ["natural_disaster", "arson", "negligence"],
    "theft": ["unlocked_vehicle", "family_member_theft"],
    "water_damage": ["natural_disaster", "gradual_leak", "flood"],
    "bodily_injury": ["self_inflicted", "pre_existing"],
}

SIMPLE_DESCRIPTIONS = [
    "Minor fender bender in parking lot, scratched bumper, no injuries.",
    "Small kitchen fire contained by homeowner, smoke damage to cabinets.",
    "Bicycle stolen from garage, value approximately 800 EUR.",
    "Water leak from washing machine, damaged laminate flooring in laundry room.",
    "Side mirror clipped by passing vehicle, mirror needs replacement.",
]

COMPLEX_DESCRIPTIONS = [
    "Multi-vehicle collision at intersection, airbags deployed, vehicle towed. Possible whiplash injury reported.",
    "Kitchen fire spread to adjacent rooms, significant smoke and water damage. Family displaced.",
    "Home burglary, electronics and jewelry stolen. Forced entry through back door.",
    "Pipe burst in second floor bathroom, water damage to ceiling and walls on first floor.",
    "Rear-end collision at traffic light, vehicle pushed into car ahead. Two passengers complaining of back pain.",
]

FRAUD_DESCRIPTIONS = [
    "Vehicle caught fire in remote location late at night. No witnesses. Photos show inconsistent damage patterns.",
    "Home fire reported 3 days after policy activation. Claim amount significantly higher than property value.",
    "Theft claim for high-value items with no receipts or proof of purchase. No police report filed.",
    "Water damage claim with description inconsistent with actual plumbing layout described.",
    "Single-vehicle accident on empty road at 3am. No police report. Claim amount 4x repair estimate.",
]

EXCLUSION_DESCRIPTIONS = [
    "Home flooded during severe storm. City declared natural disaster zone.",
    "Vehicle damaged during amateur racing event at private track.",
    "Water damage from gradual pipe leak over several months, homeowner aware but did not repair.",
]


# ─── Policy document templates (for RAG indexing) ────────────────────

POLICY_TEXT_TEMPLATES = {
    "auto": """INSURANCE POLICY — AUTOMOBILE COVERAGE

Policy ID: {policy_id}
Customer ID: {customer_id}
Policy Type: Auto Insurance
Coverage Type: {coverage_type}
Effective Date: {start_date}
Expiration Date: {end_date}
Status: {status}

SECTION 1 — COVERAGE SUMMARY
This policy provides {coverage_type} coverage for the insured vehicle with a
maximum coverage limit of {coverage_limit} EUR. The deductible applicable to
each claim is {deductible} EUR. The annual premium is {premium_annual} EUR.

SECTION 2 — COVERED PERILS
The following perils are covered under this policy:
- Collision damage to the insured vehicle
- Comprehensive damage (theft, vandalism, fire, weather)
- Liability for bodily injury to third parties
- Liability for property damage to third parties
- Medical payments up to policy limits
- Uninsured/underinsured motorist coverage

SECTION 3 — EXCLUSIONS
The following are expressly excluded from coverage:
{exclusions_text}

SECTION 4 — DEDUCTIBLE AND LIMITS
The deductible amount of {deductible} EUR applies per claim. The insurer
will pay the lesser of the actual cash value of the damaged property or
the coverage limit of {coverage_limit} EUR, minus the deductible and any
applicable depreciation.

SECTION 5 — CLAIMS PROCEDURE
The insured must report any claim within 30 days of the incident. A police
report is required for theft claims exceeding 5,000 EUR and for all bodily
injury claims. The insurer reserves the right to inspect damaged property
and to request additional documentation.

SECTION 6 — FRAUD WARNING
Any person who knowingly presents a false or fraudulent claim with intent
to defraud is guilty of insurance fraud. This may result in claim denial,
policy cancellation, and criminal prosecution.

SECTION 7 — POLICY CONDITIONS
- Premium must be paid in full for coverage to remain active.
- The insured must cooperate with the insurer's investigation.
- Subrogation rights are reserved by the insurer.
- This policy is governed by the laws of the jurisdiction where issued.
""",

    "home": """INSURANCE POLICY — HOMEOWNERS COVERAGE

Policy ID: {policy_id}
Customer ID: {customer_id}
Policy Type: Home Insurance
Coverage Type: {coverage_type}
Effective Date: {start_date}
Expiration Date: {end_date}
Status: {status}

SECTION 1 — COVERAGE SUMMARY
This policy provides {coverage_type} coverage for the insured dwelling with
a maximum coverage limit of {coverage_limit} EUR. The deductible applicable
to each claim is {deductible} EUR. The annual premium is {premium_annual} EUR.

SECTION 2 — COVERED PERILS
The following perils are covered under this policy:
- Fire and smoke damage to the dwelling and contents
- Windstorm and hail damage
- Theft and vandalism
- Water damage from sudden or accidental discharge
- Personal liability coverage
- Additional living expenses if dwelling is uninhabitable

SECTION 3 — EXCLUSIONS
The following are expressly excluded from coverage:
{exclusions_text}

SECTION 4 — DEDUCTIBLE AND LIMITS
The deductible amount of {deductible} EUR applies per claim. The insurer
will pay the lesser of the replacement cost or actual cash value of the
damaged property, up to the coverage limit of {coverage_limit} EUR, minus
the deductible and any applicable depreciation.

SECTION 5 — CLAIMS PROCEDURE
The insured must report any claim within 30 days of the incident. A police
report is required for theft claims exceeding 5,000 EUR. The insurer
reserves the right to inspect damaged property and to request additional
documentation including proof of ownership.

SECTION 6 — FRAUD WARNING
Any person who knowingly presents a false or fraudulent claim with intent
to defraud is guilty of insurance fraud. This may result in claim denial,
policy cancellation, and criminal prosecution.

SECTION 7 — POLICY CONDITIONS
- Premium must be paid in full for coverage to remain active.
- The insured must maintain the property in reasonable condition.
- The insured must cooperate with the insurer's investigation.
- Subrogation rights are reserved by the insurer.
- This policy is governed by the laws of the jurisdiction where issued.
""",
}


def generate_policy_text(policy: Policy) -> str:
    """Generate a realistic policy document text for RAG indexing.

    Args:
        policy: The Policy object.

    Returns:
        A multi-section policy document string (~3000-5000 chars).
    """
    template = POLICY_TEXT_TEMPLATES.get(policy.policy_type, POLICY_TEXT_TEMPLATES["auto"])

    exclusions_text = "\n".join(f"- {e}" for e in policy.exclusions)

    return template.format(
        policy_id=policy.policy_id,
        customer_id=policy.customer_id,
        coverage_type=policy.coverage_type,
        start_date=policy.start_date,
        end_date=policy.end_date,
        status=policy.status,
        coverage_limit=policy.coverage_limit,
        deductible=policy.deductible,
        premium_annual=policy.premium_annual,
        exclusions_text=exclusions_text,
    )


# ─── Generators ──────────────────────────────────────────────────────

def _random_date(days_ago: int) -> str:
    """Generate a date string N days ago."""
    d = datetime.now() - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d")


def _random_date_range(start_days_ago: int, end_days_ago: int) -> str:
    """Generate a date string between start_days_ago and end_days_ago."""
    span = start_days_ago - end_days_ago
    offset = random.randint(0, max(span, 0))
    d = datetime.now() - timedelta(days=end_days_ago + offset)
    return d.strftime("%Y-%m-%d")


def generate_policy(
    customer_id: str,
    policy_index: int,
    claim_type: str,
    days_ago: int = 365,
    add_exclusion: str | None = None,
) -> Policy:
    """Generate a synthetic insurance policy.

    Args:
        customer_id: Customer identifier.
        policy_index: Index for unique policy ID.
        claim_type: Type of claim this policy should cover.
        days_ago: Days since policy start (default 365 = 1 year).
        add_exclusion: Force a specific exclusion (for coverage denial tests).
    """
    pt = POLICY_TYPES[claim_type]
    exclusions = list(EXCLUSIONS[claim_type])
    if add_exclusion and add_exclusion not in exclusions:
        exclusions.append(add_exclusion)

    return Policy(
        policy_id=f"POL-{policy_index:04d}",
        customer_id=customer_id,
        policy_type=pt["policy_type"],
        coverage_type=pt["coverage_type"],
        coverage_limit=pt["limit"],
        deductible=pt["deductible"],
        premium_annual=round(pt["limit"] * 0.005, 2),
        start_date=_random_date(days_ago),
        end_date=_random_date(days_ago - 365),
        exclusions=exclusions,
        status="active" if days_ago < 365 else "active",
    )


def generate_claim(
    claim_index: int,
    policy: Policy,
    scenario: str = "simple",
) -> FNOLClaim:
    """Generate one synthetic FNOL claim with controlled scenario.

    Args:
        claim_index: Index for unique claim ID.
        policy: The policy this claim falls under.
        scenario: "simple", "complex", "fraud", "exclusion", or "missing_info".
    """
    claim_id = f"CLM-{claim_index:04d}"
    claim_type = policy.coverage_type.replace("comprehensive", "home_fire").replace("collision", "auto_collision").replace("liability", "bodily_injury")
    # Derive claim_type from policy_type
    if policy.policy_type == "auto":
        claim_type = random.choice(["auto_collision", "theft", "bodily_injury"])
    elif policy.policy_type == "home":
        claim_type = random.choice(["home_fire", "water_damage"])

    if scenario == "simple":
        desc = random.choice(SIMPLE_DESCRIPTIONS)
        amount = random.uniform(200, 2000)
        incident_days_ago = random.randint(1, 10)
        expected = "FAST_TRACK_APPROVE"
        police = random.random() > 0.7
        witnesses = random.randint(0, 2)

    elif scenario == "complex":
        desc = random.choice(COMPLEX_DESCRIPTIONS)
        amount = random.uniform(25000, 50000)  # >25k triggers ADJUSTER_REVIEW
        incident_days_ago = random.randint(1, 15)
        expected = "ADJUSTER_REVIEW"
        police = random.random() > 0.3
        witnesses = random.randint(1, 4)

    elif scenario == "fraud":
        desc = random.choice(FRAUD_DESCRIPTIONS)
        amount = random.uniform(30000, 80000)
        incident_days_ago = random.randint(1, 5)  # very recent
        expected = "SIU_REFERRAL"
        police = False  # no police report = red flag
        witnesses = 0   # no witnesses = red flag

    elif scenario == "exclusion":
        # Use the first exclusion description (natural disaster / flood)
        desc = EXCLUSION_DESCRIPTIONS[0]  # "Home flooded during severe storm..."
        amount = random.uniform(10000, 50000)
        incident_days_ago = random.randint(1, 7)
        expected = "DENY_COVERAGE"
        police = random.random() > 0.5
        witnesses = random.randint(0, 2)
        # Force claim_type to match the policy type AND trigger the exclusion
        # The description mentions "flooded" and "storm" → natural_disaster exclusion
        claim_type = "water_damage"  # matches home policy, triggers natural_disaster exclusion

    else:  # missing_info
        desc = "Claim reported but details incomplete. "
        amount = 0
        incident_days_ago = random.randint(1, 3)
        expected = "REQUEST_INFORMATION"
        police = False
        witnesses = 0

    return FNOLClaim(
        claim_id=claim_id,
        policy_id=policy.policy_id,
        customer_id=policy.customer_id,
        claim_type=claim_type,
        incident_date=_random_date(incident_days_ago),
        claim_date=_random_date(incident_days_ago - 1 if incident_days_ago > 1 else 0),
        claim_amount=round(amount, 2),
        description=desc,
        police_report_filed=police,
        witnesses_count=witnesses,
        expected_triage=expected,
        metadata={"scenario": scenario},
    )


def generate_test_claims(
    n_policies: int = 20,
    n_random_claims: int = 45,
    n_history_entries: int = 10,
    n_fraud_customers: int = 2,
    scenario_distribution: dict[str, float] | None = None,
) -> tuple[list[Policy], list[FNOLClaim], list[ClaimHistoryEntry]]:
    """Generate the full test dataset: policies, claims, and claim history.

    Generates:
      - n_policies policies (with realistic coverage, deductibles, exclusions)
      - 5 controlled test claims (one per scenario type)
      - n_random_claims random claims for bulk testing
      - Claim history with fraud patterns for certain customers

    Args:
        n_policies: Number of policies to generate (min 10).
        n_random_claims: Number of random claims (in addition to the 5 test cases).
        n_history_entries: Number of history entries for non-fraud customers.
        n_fraud_customers: Number of additional fraud-pattern customers (beyond CUS-0003).
        scenario_distribution: Weights for simple/complex/fraud scenarios.

    Returns:
        Tuple of (policies, claims, claim_history).
    """
    if n_policies < 10:
        n_policies = 10  # minimum for the 5 test cases + random pool

    if scenario_distribution is None:
        scenario_distribution = {"simple": 0.50, "complex": 0.30, "fraud": 0.20}

    random.seed(42)
    faker.seed_instance(42)

    policies: list[Policy] = []
    claims: list[FNOLClaim] = []
    claim_history: list[ClaimHistoryEntry] = []

    # Generate customers and policies
    customers = []
    for i in range(n_policies):
        cid = f"CUS-{i+1:04d}"
        customers.append(cid)
        claim_type = CLAIM_TYPES[i % len(CLAIM_TYPES)]

        # Policy 3 (index 2) will be very recent (3 days) for fraud test
        days_ago = 3 if i == 2 else random.choice([180, 365, 730])

        # Policy 4 (index 3) will have a forced exclusion
        exclusion = "natural_disaster" if i == 3 else None

        policy = generate_policy(cid, i + 1, claim_type, days_ago, exclusion)
        policies.append(policy)

    # --- 5 controlled test claims (one per scenario) ---
    # Claim 1: Simple → FAST_TRACK_APPROVE
    claims.append(generate_claim(1, policies[0], "simple"))

    # Claim 2: Complex → ADJUSTER_REVIEW
    claims.append(generate_claim(2, policies[1], "complex"))

    # Claim 3: Fraud → SIU_REFERRAL (policy 3 days old, high amount, no police report)
    claims.append(generate_claim(3, policies[2], "fraud"))

    # Claim 4: Exclusion → DENY_COVERAGE (natural disaster excluded)
    # Policy 4 (POL-0004) has "natural_disaster" exclusion
    # The claim is water_damage (matches home policy) with description mentioning "storm" and "flood"
    claims.append(generate_claim(4, policies[3], "exclusion"))

    # Claim 5: Missing info → REQUEST_INFORMATION
    claims.append(generate_claim(5, policies[4], "missing_info"))

    # --- Random claims for bulk testing ---
    claim_idx = 6
    scenarios = list(scenario_distribution.keys())
    weights = list(scenario_distribution.values())
    for _ in range(n_random_claims):
        policy = random.choice(policies[:max(10, n_policies // 2)])
        scenario = random.choices(scenarios, weights=weights, k=1)[0]
        claims.append(generate_claim(claim_idx, policy, scenario))
        claim_idx += 1

    # --- Claim history (for fraud detection) ---
    # Customer 3 (CUS-0003) has repeat claims (red flag for fraud)
    for i in range(3):
        claim_history.append(ClaimHistoryEntry(
            customer_id="CUS-0003",
            claim_id=f"CLM-HIST-{i+1:04d}",
            claim_date=_random_date_range(180, 30),
            claim_type=random.choice(["auto_collision", "theft"]),
            claim_amount=round(random.uniform(5000, 20000), 2),
            fraud_found=(i == 2),  # last one was fraud
        ))

    # Additional fraud-pattern customers
    for fc in range(n_fraud_customers):
        # Use customers 6+ (indices 5+) to avoid overlapping with test cases
        idx = 5 + fc
        if idx >= len(customers):
            break
        cid = customers[idx]
        for i in range(2):
            claim_history.append(ClaimHistoryEntry(
                customer_id=cid,
                claim_id=f"CLM-HIST-{cid[-4:]}-F{i+1}",
                claim_date=_random_date_range(180, 30),
                claim_type=random.choice(["auto_collision", "theft"]),
                claim_amount=round(random.uniform(8000, 25000), 2),
                fraud_found=(i == 1),
            ))

    # Other customers have clean history
    clean_count = 0
    for cid in customers[:max(10, n_policies // 2)]:
        if cid == "CUS-0003":
            continue
        if clean_count >= n_history_entries:
            break
        n_hist = random.randint(0, 2)
        for i in range(n_hist):
            claim_history.append(ClaimHistoryEntry(
                customer_id=cid,
                claim_id=f"CLM-HIST-{cid[-4:]}-{i+1}",
                claim_date=_random_date_range(365, 60),
                claim_type=random.choice(CLAIM_TYPES),
                claim_amount=round(random.uniform(500, 5000), 2),
                fraud_found=False,
            ))
            clean_count += 1
            if clean_count >= n_history_entries:
                break

    return policies, claims, claim_history
