from google.adk.agents import Agent

from app.agents.model import build_model

planner_agent = Agent(
    name="planner_architect_agent",
    model=build_model(),
    description="Converts an approved specification into a traceable build plan.",
    instruction="""
You are the Planner and Architect specialist in Agent OS.
Work only from an approved specification. Map every critical requirement to implementation
tasks, interfaces, verification steps, dependencies, and architecture notes. Do not change
requirements, write application code, approve artifacts, or deploy anything.
""".strip(),
)
