"""Lambda wrapper — Terminal action: CREATE_TICKET.

Called by the Step Functions CHOICE_GATE when decision == "HUMAN_REVIEW"
or as the Default branch. Creates a human review ticket.
"""


def lambda_handler(event, context):
    reason = event.get("decision_reason", "low confidence or unknown decision")
    return {
        **event,
        "final_decision": "HUMAN_REVIEW",
        "actions_executed": [{"action": "create_ticket", "reason": reason}],
        "state": "FINAL",
    }
