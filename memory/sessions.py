from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic
from uuid import uuid4
from core.exceptions import SessionNotFound, SessionCapacity


class SessionStore:
    def __init__(self, *, max_sessions=100, max_turns=6, max_chars=6000, ttl=3600, clock=monotonic):
        if any(type(n) is not int or n<=0 for n in (max_sessions,max_turns,max_chars,ttl)):
            raise ValueError("Session limits must be positive integers")
        self.max_sessions,self.max_turns,self.max_chars,self.ttl=max_sessions,max_turns,max_chars,ttl
        self.clock,self._lock,self._sessions=clock,RLock(),OrderedDict()

    def _expire(self):
        now=self.clock()
        for identifier, entry in list(self._sessions.items()):
            if now-entry["touched"]>=self.ttl: del self._sessions[identifier]

    def _entry(self,identifier):
        self._expire()
        if identifier not in self._sessions: raise SessionNotFound("会话不存在或已过期")
        entry=self._sessions[identifier]
        entry["touched"]=self.clock()
        return entry

    def create(self):
        with self._lock:
            self._expire()
            if len(self._sessions)>=self.max_sessions: raise SessionCapacity("会话数量已达上限，请删除不再使用的会话")
            identifier=uuid4().hex
            self._sessions[identifier]={"touched":self.clock(),"turns":[]}
            return identifier

    def list_sessions(self):
        with self._lock:
            self._expire()
            entries = sorted(self._sessions.items(), key=lambda pair: (pair[1]["touched"], pair[0]), reverse=True)
            return [{"session_id": identifier, "turn_count": len(entry["turns"])}
                    for identifier, entry in entries]

    def history(self,identifier):
        with self._lock: return deepcopy(self._entry(identifier)["turns"])

    def append(self,identifier,question,resolved_question,answer,answered):
        with self._lock:
            turns=self._entry(identifier)["turns"]
            turns.append({"question":question[:1000],"resolved_question":resolved_question[:1000],
                          "answer":answer[:2000],"answered":answered})
            while len(turns)>self.max_turns or sum(len(t[k]) for t in turns for k in ("question","resolved_question","answer"))>self.max_chars:
                turns.pop(0)

    def clear(self,identifier):
        with self._lock: self._entry(identifier)["turns"].clear()

    def delete(self,identifier):
        with self._lock:
            self._entry(identifier)
            del self._sessions[identifier]
