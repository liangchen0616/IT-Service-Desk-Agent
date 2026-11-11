"""Opt-in real-model API acceptance using disposable documents and sessions."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.runtime import Runtime
from core.config import ProjectConfig


def run_acceptance():
    records=[]
    with TemporaryDirectory(prefix="agent-acceptance-") as temporary:
        root=Path(temporary)
        (root/"base.txt").write_text("打印机显示离线时，检查打印机电源和网络连接，然后重新添加打印机。",encoding="utf-8")
        config=ProjectConfig(documents_dir=root,file_names=("base.txt",),index_path=root/"index.json",
                             session_backend="sqlite",session_db_path=root/"sessions.sqlite3")
        runtime=Runtime(config,root/"uploads")
        with TestClient(create_app(runtime)) as client:
            def request(method,path,**kwargs):
                response=client.request(method,path,**kwargs)
                response.raise_for_status()
                return response.json()
            session=request("POST","/sessions")["session_id"]
            content="VPN 连接失败时，先检查互联网是否可用，再检查账号密码。如果仍然失败，请完全退出 VPN 客户端，重新打开后连接。多人同时失败时，联系 IT 支持检查服务器。"
            document=request("POST","/documents",files={"file":("vpn-acceptance.txt",content.encode("utf-8"))})["document_id"]
            def chat(name,question,expected,source=None):
                result=request("POST","/chat",json={"question":question,"session_id":session})
                passed=result["answered"] is expected
                if expected and source:
                    passed=passed and any(c["source"]==source for c in result["citations"])
                if not expected: passed=passed and not result["citations"]
                record={"name":name,"passed":passed,"question":question,
                        "resolved_question":result["resolved_question"],"answered":result["answered"],
                        "answer":result["answer"],"citations":result["citations"]}
                records.append(record)
                print(name,passed,flush=True)
            chat("initial","VPN连接失败怎么办？",True,"vpn-acceptance.txt")
            chat("followup","账号密码没问题，接下来怎么操作客户端？",True,"vpn-acceptance.txt")
            chat("topic_switch","换个问题，打印机显示离线怎么办？",True,"base.txt")
            chat("unsupported","公司的报销审批额度是多少？",False)
            request("DELETE","/documents/"+document)
            chat("deleted_evidence","VPN连接失败怎么办？",False)
            archives=request("GET","/document-archives")["archives"]
            archive=next(a for a in archives if a["document_id"]==document)
            request("POST","/document-archives/"+archive["archive_id"]+"/restore")
            chat("restored_evidence","VPN连接失败怎么办？",True,"vpn-acceptance.txt")
        fresh=Runtime(config,root/"uploads",embedder=runtime.embedder)
        with TestClient(create_app(fresh)) as client:
            response=client.get("/sessions/"+session)
            response.raise_for_status()
            records.append({"name":"session_restart","passed":response.json()["turn_count"]==6})
            response=client.post("/chat",json={"question":"还是失败，多人都连接不上该找谁？","session_id":session})
            response.raise_for_status()
            result=response.json()
            records.append({"name":"restart_followup","passed":result["answered"] and any(c["source"]=="vpn-acceptance.txt" for c in result["citations"]),
                            "resolved_question":result["resolved_question"],"answer":result["answer"]})
    return {"created_at":datetime.now(timezone.utc).isoformat(),"model":config.llm_model,
            "total":len(records),"passed":sum(r["passed"] for r in records),"cases":records,
            "notes":"Synthetic temporary corpus; automatic answer/source checks, not independent factual accuracy. No user documents modified."}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Run opt-in real Ollama acceptance in temporary storage")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error("Output already exists")
    report=run_acceptance()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
    print(f"{report['passed']}/{report['total']}")
    return 0 if report["passed"]==report["total"] else 1


if __name__=="__main__":raise SystemExit(main())
