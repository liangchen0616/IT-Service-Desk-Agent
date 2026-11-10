from pathlib import Path
import tomllib
from scripts.initialize import initialize
from scripts import serve
from core.config import resolve_project_root


def test_initialize_does_not_overwrite(tmp_path):
    assert len(initialize(tmp_path)) == 3
    source=tmp_path/'data/documents/vpn_guide_zh.txt'
    source.write_text('user content',encoding='utf-8')
    assert initialize(tmp_path) == []
    assert source.read_text(encoding='utf-8') == 'user content'


def test_home_override(monkeypatch,tmp_path):
    monkeypatch.setenv('AGENT_HOME',str(tmp_path))
    assert resolve_project_root() == tmp_path


def test_server_binds_locally(monkeypatch,tmp_path):
    import uvicorn
    calls=[]
    monkeypatch.setattr(uvicorn,'run',lambda *args,**kwargs:calls.append((args,kwargs)))
    monkeypatch.setenv('AGENT_HOME','before')
    assert serve.main(['--port','8765','--data-dir',str(tmp_path)]) == 0
    assert calls[0][1] == {'host':'127.0.0.1','port':8765,'workers':1}


def test_package_uses_single_dependency_source():
    root=Path(__file__).resolve().parents[1]
    config=tomllib.loads((root/'pyproject.toml').read_text())
    assert config['tool']['setuptools']['dynamic']['dependencies']['file']==['requirements.txt']
    assert set(config['project']['scripts'])=={'it-agent-query','it-agent-ingest','it-agent-serve','it-agent-init','it-agent-documents'}
