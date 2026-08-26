from __future__ import annotations

from google.adk.apps import App

from app.agents.builder import builder_agent
from app.agents.discovery import discovery_agent
from app.agents.manager import build_manager_agent
from app.agents.planner import planner_agent
from app.agents.reviewer import reviewer_agent

root_agent = build_manager_agent(
    sub_agents=[discovery_agent, planner_agent, builder_agent, reviewer_agent]
)

app = App(root_agent=root_agent, name="app")
