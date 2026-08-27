from google.adk.agents import Agent

from app.agents.model import build_model


def build_manager_agent(*, sub_agents: list[Agent]) -> Agent:
    """Compose the Manager around registered specialists without granting tool authority."""

    return Agent(
        name="workforce_manager_agent",
        model=build_model(),
        description="Coordinates the governed software-delivery workforce.",
        instruction="""
You are the Workforce Manager in Agent OS.
Inspect the current workflow state and delegate reasoning to the correct specialist. Request
clarification or human approval when a gate is reached. Never approve your own request, write
code, mutate an approved specification, grant permissions, merge, or deploy. Agent messages are
proposals; deterministic workflow and policy services decide what may execute.
""".strip(),
        sub_agents=sub_agents,
    )
