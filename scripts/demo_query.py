import argparse
import json
import sys
from scripts.api_client import ApiClient, ClientError


def display(result):
    print(result['answer'])
    for c in result['citations']:
        if c.get('source_type') == 'web_snippet': print('公开网页摘要：')
        page = f"（第 {c['page']} 页）" if c.get('page') is not None else ""
        print(f"[{c['source_id']}] {c['source']}{page}: {c['quote']}")
    print("重写次数：", result['retry_count'])
    print("路径：", ' -> '.join(str(t.get('node','?')) for t in result['trace'] if isinstance(t,dict)))


def main(argv=None):
    parser=argparse.ArgumentParser(description='通过本地 API 查询完整知识库（含上传资料）')
    parser.add_argument('question', nargs='?')
    parser.add_argument('--session-id', help='沿用通过 sessions create 创建的会话')
    parser.add_argument('--public-web-query', help='允许发送给外部搜索服务的公开查询词')
    parser.add_argument('--json', action='store_true', help='输出完整 JSON 响应')
    parser.add_argument('--api-url', default='http://127.0.0.1:8000')
    args=parser.parse_args(argv)
    if args.public_web_query and args.question is None: parser.error("公开搜索词需要同时提供单次问题")
    options={}
    if args.session_id: options["session_id"]=args.session_id
    if args.public_web_query: options["public_web_query"]=args.public_web_query
    try:
        with ApiClient(args.api_url) as client:
            if args.question is not None:
                result=client.ask(args.question, **options)
                print(json.dumps(result,ensure_ascii=False)) if args.json else display(result)
            else:
                while True:
                    try: question=input('问题（q 退出）：').strip()
                    except EOFError: break
                    if question.lower() in {'q','quit','exit'}: break
                    if not question: continue
                    display(client.ask(question, **options))
        return 0
    except (ClientError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except KeyboardInterrupt: return 130


if __name__=='__main__': raise SystemExit(main())
