"""
CrewAI: a receipt for every agent step and every finished task.

    from sebbi.integrations.crewai import step_callback, task_callback
    crew = Crew(agents=[...], tasks=[...], step_callback=step_callback, task_callback=task_callback)
"""
from typing import Any

import sebbi


def step_callback(step: Any) -> None:
    tool = getattr(step, "tool", None)
    label = ("crewai:" + str(tool)) if tool else "crewai-step"
    sebbi.seal(getattr(step, "tool_input", None) or getattr(step, "thought", None), step, label[:80])


def task_callback(output: Any) -> None:
    desc = str(getattr(output, "description", "") or "task")
    sebbi.seal(desc, getattr(output, "raw", output), ("crewai-task:" + desc)[:80])
