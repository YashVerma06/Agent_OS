from app.contracts import ActorRole
from app.workforce import WORKFORCE


def test_reduced_workforce_has_five_distinct_roles() -> None:
    roles = {agent.role for agent in WORKFORCE}

    assert len(WORKFORCE) == 5
    assert roles == {
        ActorRole.MANAGER,
        ActorRole.DISCOVERY,
        ActorRole.PLANNER,
        ActorRole.BUILDER,
        ActorRole.REVIEWER,
    }
