def after_grade(state):
    if state.get("error"): return "fallback"
    if state["sufficient"]: return "generate"
    return "rewrite" if state["retry_count"] < 2 else "fallback"


def after_operation(next_node):
    return lambda state: "fallback" if state.get("error") else next_node
