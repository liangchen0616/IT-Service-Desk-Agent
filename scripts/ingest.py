import argparse
import json
import sys
from scripts.api_client import ApiClient, ClientError


def main(argv=None):
    parser=argparse.ArgumentParser(description='通过本地 API 上传并索引一份文档')
    parser.add_argument('file')
    parser.add_argument('--api-url',default='http://127.0.0.1:8000')
    args=parser.parse_args(argv)
    try:
        with ApiClient(args.api_url) as client:
            print(json.dumps(client.upload(args.file),ensure_ascii=False))
        return 0
    except (ClientError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except KeyboardInterrupt: return 130


if __name__=='__main__': raise SystemExit(main())
