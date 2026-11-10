"""Synchronous read-only tool execution with cooperative deadlines."""
from dataclasses import dataclass
import logging
from math import isfinite
from time import perf_counter
from typing import Any, Protocol
from pydantic import BaseModel, ValidationError
from core.exceptions import LocalModelError


@dataclass(frozen=True)
class ToolContext:
    deadline: float
    clock: Any = perf_counter

    def remaining_seconds(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise TimeoutError("Tool deadline exceeded")
        return remaining


class ReadOnlyTool(Protocol):
    name: str
    description: str
    read_only: bool
    input_model: type[BaseModel]

    def execute(self, arguments: BaseModel, context: ToolContext) -> Any: ...


@dataclass(frozen=True)
class ToolResult:
    name: str
    call_number: int
    status: str
    elapsed_ms: float
    data: Any = None
    error_code: str | None = None

    def summary(self):
        return {"name": self.name, "call_number": self.call_number,
                "status": self.status, "elapsed_ms": self.elapsed_ms,
                "error_code": self.error_code}


class ToolExecutor:
    def __init__(self, tools, *, timeout=180, max_calls=3, clock=perf_counter):
        if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError("max_calls must be a positive integer")
        self._tools = {}
        for tool in tools:
            if not tool.name or tool.name in self._tools or tool.read_only is not True:
                raise ValueError("Register unique read-only tools only")
            self._tools[tool.name] = tool
        self.timeout, self.max_calls, self.clock = timeout, max_calls, clock

    def descriptions(self):
        return [{"name": t.name, "description": t.description,
                 "parameters": t.input_model.model_json_schema()}
                for t in self._tools.values()]

    def run(self, name, arguments, *, call_number):
        start = self.clock()
        def finish(data=None, error=None):
            result = ToolResult(name, call_number, "error" if error else "ok",
                                (self.clock()-start)*1000, data, error)
            logging.getLogger("it_agent").info("tool_completed", extra={
                "tool_name": name, "tool_status": result.status,
                "tool_error_code": error, "tool_call_number": call_number,
                "elapsed_ms": result.elapsed_ms})
            return result
        if type(call_number) is not int or not 1 <= call_number <= self.max_calls:
            return finish(error="call_limit")
        tool = self._tools.get(name)
        if tool is None: return finish(error="unknown_tool")
        if not isinstance(arguments, dict): return finish(error="invalid_arguments")
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError:
            return finish(error="invalid_arguments")
        context = ToolContext(start+self.timeout, self.clock)
        try:
            context.remaining_seconds()
            data = tool.execute(parsed, context)
            context.remaining_seconds()
        except TimeoutError:
            return finish(error="timeout")
        except LocalModelError:
            return finish(error="model_error")
        except Exception as exc:
            logging.getLogger("it_agent").warning("tool_failed", extra={
                "tool_name": name, "error_type": type(exc).__name__})
            return finish(error="execution_failed")
        return finish(data=data)
