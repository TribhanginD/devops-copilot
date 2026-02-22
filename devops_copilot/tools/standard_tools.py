from devops_copilot.tools.registry import registry
from devops_copilot.core.observability import track_tool_metrics
import httpx
import json

@registry.register(name="web_search", description="Search the web for information.")
@track_tool_metrics("web_search")
def web_search(query: str) -> str:
    """Simulates a web search tool."""
    return f"Search results for: {query}. (Mocked response: Found info about Multi-Agent LLMs)"

from simpleeval import SimpleEval

@registry.register(name="calculator", description="Perform basic math operations securely.")
@track_tool_metrics("calculator")
def calculator(expression: str) -> float:
    """Evaluates a math expression securely using simpleeval."""
    try:
        s = SimpleEval()
        return float(s.eval(expression))
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"

@registry.register(name="idempotent_write", description="Write data to a file safely.")
@track_tool_metrics("idempotent_write")
def idempotent_write(filename: str, content: str) -> str:
    """An idempotent file write operation."""
    # Check if content is same to avoid unnecessary writes
    import os
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            if f.read() == content:
                return "File already contains this content. No change."
    
    with open(filename, 'w') as f:
        f.write(content)
    return f"Successfully wrote to {filename}"
