"""Tool 6 : check_coverage

Vérifie si la police couvre le type de sinistre déclaré.
Vérifie aussi les exclusions.

Input:  {"policy": {...}, "claim_type": "home_fire"}
Output: {"is_covered", "exclusion_hit", "coverage_limit", "deductible",
         "policy_active", "reason"}

Pas de LLM : règles déterministes pures.
"""

# Mapping claim_type → policy_type
CLAIM_TO_POLICY_TYPE = {
    "auto_collision": "auto",
    "theft": "auto",
    "bodily_injury": "auto",
    "home_fire": "home",
    "water_damage": "home",
}

# Exclusions that match specific claim types
EXCLUSION_MATCHES = {
    "auto_collision": ["racing", "commercial_use", "intentional_damage"],
    "home_fire": ["natural_disaster", "arson", "negligence"],
    "theft": ["unlocked_vehicle", "family_member_theft"],
    "water_damage": ["natural_disaster", "gradual_leak", "flood"],
    "bodily_injury": ["self_inflicted", "pre_existing"],
}

# Keywords in claim description that trigger exclusion checks
EXCLUSION_KEYWORDS = {
    "natural_disaster": ["storm", "flood", "hurricane", "earthquake", "natural disaster"],
    "racing": ["racing", "race track", "track day"],
    "gradual_leak": ["gradual", "slow leak", "over months", "over several months"],
    "arson": ["arson", "intentionally set", "deliberately"],
}


def check_coverage(policy: dict, claim_type: str, description: str = "") -> dict:
    """Check if the policy covers the claim type and no exclusions apply.

    Args:
        policy: Policy data (from check_policy).
        claim_type: The type of claim (e.g. "home_fire").
        description: Claim description (for exclusion keyword matching).

    Returns:
        Dict with coverage assessment.
    """
    # Check if policy is active
    if not policy.get("is_active", False):
        return {
            "is_covered": False,
            "exclusion_hit": None,
            "coverage_limit": policy.get("coverage_limit", 0),
            "deductible": policy.get("deductible", 0),
            "policy_active": False,
            "reason": f"Policy status is '{policy.get('status', 'unknown')}', not active",
        }

    # Check if claim type matches policy type
    expected_policy_type = CLAIM_TO_POLICY_TYPE.get(claim_type)
    actual_policy_type = policy.get("policy_type", "")
    if expected_policy_type and expected_policy_type != actual_policy_type:
        return {
            "is_covered": False,
            "exclusion_hit": None,
            "coverage_limit": policy.get("coverage_limit", 0),
            "deductible": policy.get("deductible", 0),
            "policy_active": True,
            "reason": f"Claim type '{claim_type}' requires {expected_policy_type} policy, but policy is {actual_policy_type}",
        }

    # Check exclusions
    exclusions = policy.get("exclusions", [])
    desc_lower = description.lower()

    for exclusion in exclusions:
        # Direct exclusion match
        applicable_to = EXCLUSION_MATCHES.get(claim_type, [])
        if exclusion in applicable_to:
            # Check if description contains keywords that trigger this exclusion
            keywords = EXCLUSION_KEYWORDS.get(exclusion, [])
            if keywords and any(kw in desc_lower for kw in keywords):
                return {
                    "is_covered": False,
                    "exclusion_hit": exclusion,
                    "coverage_limit": policy.get("coverage_limit", 0),
                    "deductible": policy.get("deductible", 0),
                    "policy_active": True,
                    "reason": f"Claim excluded by policy exclusion: '{exclusion}'",
                }

    # All checks passed
    return {
        "is_covered": True,
        "exclusion_hit": None,
        "coverage_limit": policy.get("coverage_limit", 0),
        "deductible": policy.get("deductible", 0),
        "policy_active": True,
        "reason": "Coverage confirmed",
    }
