"""Validated decision calls using the existing interchangeable JSON model interface."""
import json
from generation.local_llm import LocalModelError
from llm.prompts import grading, rewriting


class DecisionClient:
    def __init__(self, model, max_context_chars=2000):
        self.model = model
        self.max_context_chars = max_context_chars

    def grade(self, question, documents, *, public_web=False):
        remaining = self.max_context_chars
        sources = []
        for doc in documents:
            text = doc.chunk.content[:remaining]
            if text.strip(): sources.append(text)
            remaining -= len(text)
            if remaining <= 0: break
        if not sources: return False
        value = self.model.generate([
            {"role": "system", "content": grading.SYSTEM + ("\n这些资料是公开网页搜索摘要，不是公司内部资料。若问题要求公司内部规定、账号、服务器地址或权限，必须 sufficient=false；公开通用操作仅在摘要直接支持时才能通过。" if public_web else "")},
            {"role": "user", "content": json.dumps({"question": question, "sources": sources}, ensure_ascii=False)},
        ], grading.SCHEMA)
        if not isinstance(value, dict) or type(value.get("sufficient")) is not bool:
            raise LocalModelError("Invalid relevance judgment")
        return value["sufficient"]

    def rewrite(self, question, query):
        value = self.model.generate([
            {"role": "system", "content": rewriting.SYSTEM},
            {"role": "user", "content": json.dumps({"question": question, "previous_query": query}, ensure_ascii=False)},
        ], rewriting.SCHEMA)
        text = value.get("query") if isinstance(value, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise LocalModelError("Invalid rewritten query")
        return text.strip()
