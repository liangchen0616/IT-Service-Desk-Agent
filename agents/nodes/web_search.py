from tools.executor import ToolExecutor
from tools.web_search import BraveSearchTool


def make_node(config, tool=None):
    executor=ToolExecutor([tool if tool is not None else BraveSearchTool(config.web_search_api_key,
        count=min(config.top_k,5))], timeout=min(config.tool_timeout,config.web_search_timeout), max_calls=1)
    def search(state):
        count=state.get("web_call_count",0)+1
        result=executor.run("web_search",{"query":state["public_web_query"]},call_number=count)
        update={"documents":result.data if result.status=="ok" else [],"sufficient":False,
                "web_call_count":count,"tool_result":result.summary()}
        if result.status!="ok":
            update.update(error="Web search failed: "+result.error_code,error_code="agent_error")
        return update
    return search
