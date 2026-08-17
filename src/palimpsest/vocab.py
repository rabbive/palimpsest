"""Closed predicate vocabulary for fact extraction.

Load-bearing: the extractor must choose from this list (or emit OTHER), and the
coverage/abstention check matches slots against these exact strings. Derived from
a skim of BEAM-100K dialogues 1-2 (personal-life domain: profession, location,
projects, deadlines, tools, relationships, preferences).
"""

PREDICATES = [
    "LIVES_IN",
    "MOVED_FROM",
    "WORKS_AT",
    "HAS_PROFESSION",
    "REPORTS_TO",
    "MANAGES",
    "OWNS",
    "PREFERS",
    "DISLIKES",
    "HAS_DEADLINE",
    "SCHEDULED_FOR",
    "RESCHEDULED_TO",
    "USES_TOOL",
    "STOPPED_USING_TOOL",
    "WORKING_ON_PROJECT",
    "COMPLETED_PROJECT",
    "ABANDONED_PROJECT",
    "HAS_GOAL",
    "ACHIEVED_GOAL",
    "HAS_BUDGET",
    "SPENT_AMOUNT",
    "ATTENDED",
    "PLANS_TO_ATTEND",
    "DECIDED",
    "RECOMMENDED",
    "RECEIVED_FEEDBACK",
    "HAS_RELATIONSHIP_WITH",
    "MARRIED_TO",
    "HAS_CHILD",
    "HAS_PET",
    "HAS_HEALTH_CONDITION",
    "TAKES_MEDICATION",
    "HAS_SKILL",
    "LEARNING_SKILL",
    "HAS_HOBBY",
    "MEMBER_OF",
    "HAS_AGE",
    "HAS_CONTACT_INFO",
    "COLLABORATES_WITH",
    "OTHER",
]

PREDICATE_SET = set(PREDICATES)


def is_valid_predicate(predicate: str) -> bool:
    return predicate in PREDICATE_SET
