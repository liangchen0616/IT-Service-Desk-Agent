import argparse
import json
import re
import sys
from scripts.api_client import ApiClient, ClientError


def main(argv=None):
    parser=argparse.ArgumentParser(description="管理本地问答会话")
    parser.add_argument("--api-url",default="http://127.0.0.1:8000")
    commands=parser.add_subparsers(dest="action",required=True)
    commands.add_parser("create")
    for action in ("show","clear","delete"):
        commands.add_parser(action).add_argument("session_id")
    args=parser.parse_args(argv)
    if args.action!="create" and not re.fullmatch(r"[0-9a-f]{32}",args.session_id):
        parser.error("请输入创建会话时返回的编号")
    method={"create":"POST","show":"GET","clear":"DELETE","delete":"DELETE"}[args.action]
    path="/sessions" if args.action=="create" else "/sessions/"+args.session_id
    if args.action=="clear": path+="/history"
    try:
        with ApiClient(args.api_url) as client: print(json.dumps(client.request(method,path),ensure_ascii=False))
        return 0
    except (ClientError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except KeyboardInterrupt: return 130


if __name__=="__main__": raise SystemExit(main())
