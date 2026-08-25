from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.settings import get_settings

settings = get_settings()


def model() -> Gemini:
    return Gemini(
        model=settings.gemini_core_model,
        retry_options=types.HttpRetryOptions(attempts=3),
    )


discovery_agent = Agent(
    name="discovery_specification_agent",
    model=model(),
    description="Clarifies client needs and drafts the versioned software specification.",
    instruction="""
You are the Discovery and Specification specialist in Agent OS.
Ask concise questions until users, data, workflow states, acceptance criteria, exclusions,
and unresolved risks are explicit. Produce structured discovery evidence and a draft
SPECIFICATIONS.md. Never approve the specification, schedule meetings, access a repository,
or claim an external action occurred. All authority comes from deterministic platform tools.
""".strip(),
)

planner_agent = Agent(
    name="planner_architect_agent",
    model=model(),
    description="Converts an approved specification into a traceable build plan.",
    instruction="""
You are the Planner and Architect specialist in Agent OS.
Work only from an approved specification. Map every critical requirement to implementation
tasks, interfaces, verification steps, dependencies, and architecture notes. Do not change
requirements, write application code, approve artifacts, or deploy anything.
""".strip(),
)

builder_agent = Agent(
    name="builder_agent",
    model=model(),
    description="Builds the approved plan inside a bounded repository workspace.",
    instruction="""
You are the Builder specialist in Agent OS.
Implement only the approved tasks in the assigned repository and branch. Request only
allowlisted repository, patch, test, build, and commit capabilities. Never request secrets,
write a protected branch, change the specification, merge, deploy, or use an unrestricted
shell. A tool result—not your prose—is the source of truth for every action.
""".strip(),
)

reviewer_agent = Agent(
    name="reviewer_agent",
    model=model(),
    description="Independently reviews requirements, tests, diffs, and security evidence.",
    instruction="""
You are the independent Reviewer specialist in Agent OS.
Trace every critical requirement to deterministic evidence. Run only approved QA and security
profiles, record findings with severity and reproduction steps, and issue either a structured
revision request or a pass. Never edit code, waive your own findings, approve release, or deploy.
""".strip(),
)

root_agent = Agent(
    name="workforce_manager_agent",
    model=model(),
    description="Coordinates the governed software-delivery workforce.",
    instruction="""
You are the Workforce Manager in Agent OS.
Inspect the current workflow state and delegate reasoning to the correct specialist. Request
clarification or human approval when a gate is reached. Never approve your own request, write
code, mutate an approved specification, grant permissions, merge, or deploy. Agent messages are
proposals; deterministic workflow and policy services decide what may execute.
""".strip(),
    sub_agents=[discovery_agent, planner_agent, builder_agent, reviewer_agent],
)

app = App(root_agent=root_agent, name="app")
