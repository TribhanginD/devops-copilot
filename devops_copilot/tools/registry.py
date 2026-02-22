from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, ConfigDict, Field, create_model, validate_call
import inspect
from devops_copilot.utils.logger import logger

class Tool(BaseModel):
    """Represents a tool available to agents."""
    name: str
    description: str
    parameters_schema: Type[BaseModel]
    func: Callable
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def execute(self, **kwargs) -> Any:
        """
        Executes the tool with validation.
        IMPORTANT: All arguments are validated against parameters_schema before execution.
        """
        logger.info(f"Executing tool: {self.name} with params: {kwargs}")
        validated_params = self.parameters_schema(**kwargs)
        return self.func(**validated_params.model_dump())

class ToolRegistry:
    """Registry for managing and validating tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str):
        """Decorator to register a function as a tool."""
        def decorator(func: Callable):
            # Create a Pydantic model from the function signature
            sig = inspect.signature(func)
            fields = {}
            for param_name, param in sig.parameters.items():
                if param.annotation == inspect.Parameter.empty:
                    fields[param_name] = (Any, ...)
                else:
                    fields[param_name] = (param.annotation, ... if param.default == inspect.Parameter.empty else param.default)
            
            pydantic_model = create_model(f"{func.__name__}_Schema", **fields)
            
            tool = Tool(
                name=name,
                description=description,
                parameters_schema=pydantic_model,
                func=func
            )
            self._tools[name] = tool
            logger.info(f"Registered tool: {name}")
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema.model_json_schema()
            }
            for tool in self._tools.values()
        ]

# Global registry instance
registry = ToolRegistry()
