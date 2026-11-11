"""Manage uploaded documents through the local API."""
import argparse
import json
import re
import sys
from scripts.api_client import ApiClient, ClientError


def main(argv=None):
    parser = argparse.ArgumentParser(description="查看和移除已上传的知识库文档")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("list")
    commands.add_parser("archives")
    commands.add_parser("restore").add_argument("archive_id")
    for action in ("show", "delete"):
        command = commands.add_parser(action)
        command.add_argument("document_id")
    args = parser.parse_args(argv)
    if args.action in {"show","delete"} and not re.fullmatch(r"[0-9a-f]{32}", args.document_id):
        parser.error("请使用上传或列表返回的 32 位文档编号")
    method = "DELETE" if args.action == "delete" else "GET"
    if args.action=="restore":
        if not re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{32}",args.archive_id):
            parser.error("请使用归档列表返回的编号")
        method,path="POST","/document-archives/"+args.archive_id+"/restore"
    elif args.action=="archives": path="/document-archives"
    else: path = "/documents" + ("" if args.action == "list" else "/" + args.document_id)
    try:
        with ApiClient(args.api_url) as client:
            print(json.dumps(client.request(method, path), ensure_ascii=False))
        return 0
    except (ClientError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__": raise SystemExit(main())
