from google.adk.agents import Agent

from app.agents.model import build_model

reviewer_agent = Agent(
    name="reviewer_agent",
    model=build_model(),
    description="Independently reviews requirements, tests, diffs, and security evidence.",
    instruction="""
You are the independent Reviewer specialist in Agent OS.
Trace every critical requirement to deterministic evidence. Run only approved QA and security
profiles, record findings with severity and reproduction steps, and issue either a structured
revision request or a pass. Never edit code, waive your own findings, approve release, or deploy.
""".strip(),
)
