"""Initialize writable local data without touching existing files."""
import argparse
from importlib.resources import files
from pathlib import Path
import sys


def initialize(destination):
    destination = Path(destination).expanduser().resolve()
    documents = destination / 'data' / 'documents'
    documents.mkdir(parents=True, exist_ok=True)
    resources = files('core').joinpath('resources')
    created = []
    entries = [(resources.joinpath(name), documents/name) for name in ('vpn_guide_zh.txt','printer_guide_zh.txt')]
    entries.append((resources.joinpath('settings.example'),destination/'.env.example'))
    for source, target in entries:
        try:
            with target.open('xb') as handle: handle.write(source.read_bytes())
        except FileExistsError: continue
        created.append(target)
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(description='准备示例文档，不覆盖已有文件')
    parser.add_argument('--data-dir',type=Path)
    args = parser.parse_args(argv)
    from core.config import PROJECT_ROOT
    destination = args.data_dir or PROJECT_ROOT
    try:
        created = initialize(destination)
        print(f"数据目录：{destination.resolve()}；新增文件：{len(created)}")
        return 0
    except OSError as exc:
        print(f"初始化失败：{exc}",file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
