"""Opt-in Brave search snippets; never fetch arbitrary result pages."""
from html import unescape
import json
import re
from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ingestion.chunker import Chunk
from retrieval.contracts import RetrievedChunk


class WebArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=600)

    @field_validator("query")
    @classmethod
    def valid_query(cls, value):
        if not value.strip() or len(value.split()) > 75:
            raise ValueError("Invalid public query")
        return value.strip()


def plain_text(value):
    return unescape(re.sub(r"<[^>]*>", "", value)).strip()


class BraveSearchTool:
    name = "web_search"
    description = "Search public web snippets with an explicitly supplied public query."
    read_only = True
    input_model = WebArguments
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key, *, count=3, transport=None):
        self._api_key, self.count, self.transport = api_key, count, transport

    def execute(self, arguments, context):
        if not self._api_key: raise ValueError("Search credentials missing")
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, transport=self.transport,
                              timeout=context.remaining_seconds()) as client:
                with client.stream("GET", self.endpoint,
                    params={"q":arguments.query,"count":self.count,"text_decorations":"false"},
                    headers={"X-Subscription-Token":self._api_key,"Accept":"application/json"}) as response:
                    if response.status_code != 200: raise ValueError("Search service failed")
                    raw=bytearray()
                    for block in response.iter_bytes():
                        context.remaining_seconds()
                        raw.extend(block)
                        if len(raw)>1_000_000: raise ValueError("Search response too large")
            payload=json.loads(raw)
        except httpx.TimeoutException:
            raise TimeoutError("Search timed out") from None
        if not isinstance(payload,dict): raise ValueError("Invalid search response")
        web=payload.get("web")
        if web is None: return []
        if not isinstance(web,dict) or not isinstance(web.get("results"),list):
            raise ValueError("Invalid search results")
        results=[]; seen=set()
        for entry in web["results"]:
            if not isinstance(entry,dict): continue
            url, description = entry.get("url"), entry.get("description")
            if not isinstance(url,str) or not isinstance(description,str): continue
            try:
                parsed=urlsplit(url)
                if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
                    continue
            except ValueError: continue
            if any(ord(c)<32 for c in url) or url in seen: continue
            text=plain_text(description)[:1500]
            if not text: continue
            title=plain_text(entry.get("title") or "") if isinstance(entry.get("title"),str) else ""
            metadata={"source":url,"url":url,"title":title[:300],"source_type":"web_snippet"}
            results.append(RetrievedChunk(Chunk(text,metadata,len(results),0,len(text)),
                                          1./(len(results)+1),"web_rank"))
            seen.add(url)
            if len(results)>=self.count: break
        return results
