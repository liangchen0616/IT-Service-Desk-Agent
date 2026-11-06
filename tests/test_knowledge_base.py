import json
from dataclasses import FrozenInstanceError, replace

import pytest

import ingestion.knowledge_base as builder
from embeddings.embedder import EmbeddedChunk
from evaluation.evaluate_retrieval import evaluate_cases, load_cases, save_report
from project_config import ProjectConfig


class FakeEmbedder:
    def embed_chunks(self, chunks):
        self.chunks = chunks
        return [EmbeddedChunk(chunk, [1.0, 0.0]) for chunk in chunks]

    def embed_query(self, query):
        return [1.0, 0.0]


@pytest.fixture
def config(tmp_path):
    (tmp_path / "guide.txt").write_text("第一句。第二句。第三句。", encoding="utf-8")
    (tmp_path / "other.md").write_text("另一个主题。", encoding="utf-8")
    return ProjectConfig(documents_dir=tmp_path, file_names=("guide.txt", "other.md"), chunk_size=9, overlap=4)


@pytest.mark.parametrize("mode", ["boundary", "fixed"])
def test_builder_preserves_sources_and_allows_search(config, mode):
    embedder = FakeEmbedder()
    knowledge = builder.build_knowledge_base(replace(config, chunk_mode=mode), embedder)
    assert knowledge.document_count == 2
    assert knowledge.chunk_count == len(embedder.chunks)
    assert knowledge.retriever.store.count() == knowledge.chunk_count
    assert {chunk.metadata["source"] for chunk in embedder.chunks} == {"guide.txt", "other.md"}
    result = knowledge.retriever.retrieve("问题", top_k=1)[0]
    assert result.chunk is embedder.chunks[0]


def test_model_is_constructed_once_with_configured_name(config, monkeypatch):
    calls = []
    def make_embedder(model_name):
        calls.append(model_name)
        return FakeEmbedder()
    monkeypatch.setattr(builder, "LocalEmbedder", make_embedder)
    knowledge = builder.build_knowledge_base(config)
    knowledge.retriever.retrieve("第一个问题")
    knowledge.retriever.retrieve("第二个问题")
    assert calls == [config.model_name]


@pytest.mark.parametrize("blank", [False, True])
def test_invalid_documents_fail_before_loading_model(config, monkeypatch, blank):
    def unexpected_model(**kwargs):
        pytest.fail("Model should not load for invalid documents.")
    monkeypatch.setattr(builder, "LocalEmbedder", unexpected_model)
    if blank:
        path = config.documents_dir / "blank.txt"
        path.write_text("  \n", encoding="utf-8")
        selected = replace(config, file_names=("blank.txt",))
        error = ValueError
    else:
        selected = replace(config, file_names=("missing.txt",))
        error = FileNotFoundError
    with pytest.raises(error):
        builder.build_knowledge_base(selected)


@pytest.mark.parametrize("changes, error", [
    ({"chunk_size": 0}, ValueError),
    ({"overlap": 300}, ValueError),
    ({"top_k": True}, TypeError),
    ({"top_k": 0}, ValueError),
    ({"chunk_mode": "unknown"}, ValueError),
    ({"min_score": float("nan")}, ValueError),
    ({"min_score": 2}, ValueError),
    ({"min_score": "0.5"}, TypeError),
    ({"file_names": ()}, ValueError),
    ({"file_names": ("guide.txt", "guide.txt")}, ValueError),
    ({"file_names": ("../guide.txt",)}, ValueError),
    ({"file_names": ("file.exe",)}, ValueError),
])
def test_invalid_config_is_rejected(changes, error):
    with pytest.raises(error):
        ProjectConfig(**changes)


def test_config_cannot_be_changed_in_place(config):
    with pytest.raises(FrozenInstanceError):
        config.chunk_size = 1


def test_evaluation_records_success_failure_and_no_results(config):
    knowledge = builder.build_knowledge_base(config, FakeEmbedder())
    cases = [
        {"query": "问题一", "expected_source": "guide.txt"},
        {"query": "问题二", "expected_source": "other.md"},
        {"query": "问题三", "expected_source": None},
    ]
    report = evaluate_cases(cases, knowledge.retriever, config)
    assert report["total"] == 3
    assert report["passed"] == 1
    assert report["chunk_mode"] == config.chunk_mode
    assert report["cases"][0]["top_content"]
    class EmptyRetriever:
        def retrieve(self, query, **kwargs):
            return []
    empty = evaluate_cases(cases, EmptyRetriever(), config)
    assert empty["passed"] == 1
    assert empty["cases"][0]["top_score"] is None


def test_cases_and_report_round_trip(tmp_path):
    cases = [{"query": "中文问题", "expected_source": None}]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    assert load_cases(path) == cases
    report = {"cases": cases, "passed": 0}
    output = tmp_path / "reports" / "report.json"
    save_report(report, output)
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert "中文问题" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("cases", [[], {}, [{"query": "", "expected_source": None}], [{"query": "问题"}]])
def test_bad_cases_are_rejected(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)
