import argparse
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description='启动本地单进程知识库 API')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--data-dir',type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('port must be between 1 and 65535')
    if args.data_dir is not None:
        os.environ['AGENT_HOME'] = str(args.data_dir.expanduser().resolve())
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port,workers=1)
    return 0


if __name__ == '__main__': raise SystemExit(main())
