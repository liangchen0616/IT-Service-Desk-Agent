"""Optional SQLite history; one short transaction per store operation."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from time import time
from uuid import uuid4
from core.exceptions import SessionNotFound, SessionCapacity
from memory.sessions import SessionStore


class SQLiteSessionStore:
    def __init__(self,path,*,max_sessions=100,max_turns=6,max_chars=6000,ttl=3600,clock=time):
        SessionStore(max_sessions=max_sessions,max_turns=max_turns,max_chars=max_chars,ttl=ttl)
        self.path=Path(path)
        self.max_sessions,self.max_turns,self.max_chars,self.ttl=max_sessions,max_turns,max_chars,ttl
        self.clock=clock

    @contextmanager
    def _transaction(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        connection=sqlite3.connect(self.path,timeout=10)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS agent_sessions (id TEXT PRIMARY KEY, touched REAL NOT NULL, turns TEXT NOT NULL)")
            connection.execute("DELETE FROM agent_sessions WHERE touched <= ?",(self.clock()-self.ttl,))
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally: connection.close()

    def _read(self,connection,identifier):
        row=connection.execute("SELECT turns FROM agent_sessions WHERE id=?",(identifier,)).fetchone()
        if row is None: raise SessionNotFound("会话不存在或已过期")
        turns=json.loads(row[0])
        if not isinstance(turns,list): raise ValueError("Invalid session history")
        return turns

    def _write(self,connection,identifier,turns):
        connection.execute("UPDATE agent_sessions SET touched=?, turns=? WHERE id=?",
                           (self.clock(),json.dumps(turns,ensure_ascii=False),identifier))

    def create(self):
        with self._transaction() as connection:
            if connection.execute("SELECT COUNT(*) FROM agent_sessions").fetchone()[0]>=self.max_sessions:
                raise SessionCapacity("会话数量已达上限，请删除不再使用的会话")
            identifier=uuid4().hex
            connection.execute("INSERT INTO agent_sessions VALUES (?,?,?)",(identifier,self.clock(),"[]"))
            return identifier

    def history(self,identifier):
        with self._transaction() as connection:
            turns=self._read(connection,identifier)
            self._write(connection,identifier,turns)
            return turns

    def append(self,identifier,question,resolved_question,answer,answered):
        with self._transaction() as connection:
            turns=self._read(connection,identifier)
            turns.append({"question":question[:1000],"resolved_question":resolved_question[:1000],
                          "answer":answer[:2000],"answered":answered})
            while len(turns)>self.max_turns or sum(len(t[k]) for t in turns for k in ("question","resolved_question","answer"))>self.max_chars:
                turns.pop(0)
            self._write(connection,identifier,turns)

    def clear(self,identifier):
        with self._transaction() as connection:
            self._read(connection,identifier)
            self._write(connection,identifier,[])

    def delete(self,identifier):
        with self._transaction() as connection:
            self._read(connection,identifier)
            connection.execute("DELETE FROM agent_sessions WHERE id=?",(identifier,))
