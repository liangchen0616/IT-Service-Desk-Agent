import json
from dataclasses import replace

import pytest

import ingestion.knowledge_base as builder
import vectorstore.json_store as storage
from embeddings.embedder import EmbeddedChunk
from ingestion.chunker import Chunk
from project_config import ProjectConfig
from vectorstore.json_store import IndexMismatchError, JsonVectorStore


class FakeEmbedder:
    """Count indexing work without downloading or running a real model."""

    def __init__(self):
        self.document_calls = 0

    def embed_chunks(self, chunks):
        self.document_calls += 1
        return [
            EmbeddedChunk(chunk, [1.0, 0.0] if chunk.metadata["source"] == "vpn.txt" else [0.0, 1.0])
            for chunk in chunks
        ]

    def embed_query(self, query):
        return [1.0, 0.0]


@pytest.fixture
def config(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "vpn.txt").write_text("公司 VPN 无法连接。检查网络和账号。", encoding="utf-8")
    (documents / "printer.md").write_text("打印机显示离线。检查打印机网络。", encoding="utf-8")
    return ProjectConfig(
        documents_dir=documents,
        file_names=("vpn.txt", "printer.md"),
        index_path=tmp_path / "indexes" / "knowledge.json",
    )


@pytest.fixture
def store():
    result = JsonVectorStore()
    result.add([
        EmbeddedChunk(Chunk("VPN 指南", {"source": "vpn.txt", "tags": ["网络"]}, 0, 3, 9), [2.0, 0.0]),
        EmbeddedChunk(Chunk("打印指南", {"source": "printer.md"}, 1, 0, 4), [0.0, 3.0]),
    ])
    return result


def test_json_round_trip_preserves_ranking_text_metadata_and_offsets(store, tmp_path):
    path = tmp_path / "index.json"
    store.save(path, "test-model", "snapshot")
    restored = JsonVectorStore.load(path, "test-model", "snapshot")
    before = store.search([1.0, 0.0])
    after = restored.search([1.0, 0.0])
    assert after == before
    assert restored.count() == 2
    assert after[0].chunk.start_index == 3
    assert after[0].chunk.metadata["tags"] == ["网络"]
    assert "VPN 指南" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("model,signature", [("other", "snapshot"), ("test-model", "other")])
def test_mismatched_index_is_reported_separately(store, tmp_path, model, signature):
    path = tmp_path / "index.json"
    store.save(path, "test-model", "snapshot")
    with pytest.raises(IndexMismatchError):
        JsonVectorStore.load(path, model, signature)


@pytest.mark.parametrize("damage", [
    "wrong_version", "boolean_version", "missing_model", "missing_signature",
    "empty_items", "bad_record", "blank_content", "missing_source", "bad_metadata",
    "negative_index", "boolean_index", "wrong_offsets", "empty_vector", "zero_vector",
    "nan_vector", "infinite_vector", "string_vector", "boolean_vector", "wrong_dimension",
])
def test_corrupt_index_is_rejected_with_rebuild_instructions(store, tmp_path, damage):
    path = tmp_path / "index.json"
    store.save(path, "test-model", "snapshot")
    payload = json.loads(path.read_text(encoding="utf-8"))
    item = payload["items"][0]
    if damage == "wrong_version":
        payload["format_version"] = 99
    elif damage == "boolean_version":
        payload["format_version"] = True
    elif damage == "missing_model":
        payload.pop("model_name")
    elif damage == "missing_signature":
        payload.pop("signature")
    elif damage == "empty_items":
        payload["items"] = []
    elif damage == "bad_record":
        payload["items"] = [None]
    elif damage == "blank_content":
        item["chunk"]["content"] = " "
    elif damage == "missing_source":
        item["chunk"]["metadata"] = {}
    elif damage == "bad_metadata":
        item["chunk"]["metadata"] = []
    elif damage == "negative_index":
        item["chunk"]["chunk_index"] = -1
    elif damage == "boolean_index":
        item["chunk"]["start_index"] = True
    elif damage == "wrong_offsets":
        item["chunk"]["end_index"] += 1
    else:
        item["vector"] = {
            "empty_vector": [], "zero_vector": [0.0, 0.0],
            "nan_vector": [float("nan"), 0.0],
            "infinite_vector": [float("inf"), 0.0],
            "string_vector": ["1", 0.0], "boolean_vector": [True, 0.0],
            "wrong_dimension": [1.0, 0.0, 0.0],
        }[damage]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="python -m ingestion.build_index"):
        JsonVectorStore.load(path, "test-model", "snapshot")


@pytest.mark.parametrize("text", ["{", "null", "[]"])
def test_invalid_json_is_rejected(tmp_path, text):
    path = tmp_path / "broken.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="Saved index is invalid"):
        JsonVectorStore.load(path, "model", "signature")


def test_failed_replace_keeps_previous_file_and_removes_temporary_file(store, tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    store.save(path, "model", "old")
    original = path.read_bytes()
    def fail_replace(source, target):
        raise OSError("simulated write failure")
    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        store.save(path, "model", "new")
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["index.json"]


def test_unserializable_metadata_does_not_replace_previous_index(store, tmp_path):
    path = tmp_path / "index.json"
    store.save(path, "model", "old")
    original = path.read_bytes()
    store.add([EmbeddedChunk(Chunk("新", {"source": "new.txt", "bad": object()}, 0, 0, 1), [1.0, 0.0])])
    with pytest.raises(TypeError):
        store.save(path, "model", "new")
    assert path.read_bytes() == original


def test_second_build_skips_document_loading_and_document_embedding(config, monkeypatch):
    embedder = FakeEmbedder()
    first = builder.build_knowledge_base(config, embedder, use_cache=True)
    def unexpected_load(selected):
        pytest.fail("A matching index must not reload and chunk the documents.")
    monkeypatch.setattr(builder, "load_documents", unexpected_load)
    second = builder.build_knowledge_base(config, embedder, use_cache=True)
    assert not first.loaded_from_cache
    assert second.loaded_from_cache
    assert embedder.document_calls == 1
    assert second.chunk_count == first.chunk_count
    assert second.retriever.retrieve("VPN", min_score=0.5) == first.retriever.retrieve("VPN", min_score=0.5)


def test_cached_start_still_loads_query_model_once(config, monkeypatch):
    builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True)
    model_calls = []
    def make_embedder(model_name):
        model_calls.append(model_name)
        return FakeEmbedder()
    monkeypatch.setattr(builder, "LocalEmbedder", make_embedder)
    knowledge = builder.build_knowledge_base(config, use_cache=True)
    knowledge.retriever.retrieve("第一个问题")
    knowledge.retriever.retrieve("第二个问题")
    assert knowledge.loaded_from_cache
    assert model_calls == [config.model_name]


def test_document_content_change_triggers_rebuild(config):
    embedder = FakeEmbedder()
    builder.build_knowledge_base(config, embedder, use_cache=True)
    (config.documents_dir / "vpn.txt").write_text("新 VPN 指南。", encoding="utf-8")
    knowledge = builder.build_knowledge_base(config, embedder, use_cache=True)
    assert not knowledge.loaded_from_cache
    assert embedder.document_calls == 2
    assert knowledge.retriever.retrieve("VPN", top_k=1)[0].chunk.content == "新 VPN 指南。"


@pytest.mark.parametrize("changes", [
    {"chunk_mode": "fixed"}, {"chunk_size": 200}, {"overlap": 0},
    {"model_name": "another-model"}, {"file_names": ("vpn.txt",)},
])
def test_vector_producing_setting_changes_trigger_rebuild(config, changes):
    embedder = FakeEmbedder()
    builder.build_knowledge_base(config, embedder, use_cache=True)
    knowledge = builder.build_knowledge_base(replace(config, **changes), embedder, use_cache=True)
    assert not knowledge.loaded_from_cache
    assert embedder.document_calls == 2


def test_pipeline_version_change_triggers_rebuild(config, monkeypatch):
    embedder = FakeEmbedder()
    builder.build_knowledge_base(config, embedder, use_cache=True)
    monkeypatch.setattr(builder, "PIPELINE_VERSION", builder.PIPELINE_VERSION + 1)
    knowledge = builder.build_knowledge_base(config, embedder, use_cache=True)
    assert not knowledge.loaded_from_cache
    assert embedder.document_calls == 2


@pytest.mark.parametrize("changes", [{"top_k": 1}, {"min_score": 0.8}])
def test_retrieval_setting_changes_reuse_index(config, changes):
    embedder = FakeEmbedder()
    builder.build_knowledge_base(config, embedder, use_cache=True)
    knowledge = builder.build_knowledge_base(replace(config, **changes), embedder, use_cache=True)
    assert knowledge.loaded_from_cache
    assert embedder.document_calls == 1


def test_explicit_rebuild_works_even_for_corrupt_index(config):
    config.index_path.parent.mkdir(parents=True)
    config.index_path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="Saved index is invalid"):
        builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True)
    knowledge = builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True, force_rebuild=True)
    assert not knowledge.loaded_from_cache
    assert JsonVectorStore.load(config.index_path, config.model_name, builder.compute_signature(config)).count() == knowledge.chunk_count


def test_force_rebuild_regenerates_unchanged_documents(config):
    embedder = FakeEmbedder()
    builder.build_knowledge_base(config, embedder, use_cache=True)
    builder.build_knowledge_base(config, embedder, use_cache=True, force_rebuild=True)
    assert embedder.document_calls == 2


def test_legacy_memory_only_build_does_not_write_to_disk(config):
    knowledge = builder.build_knowledge_base(config, FakeEmbedder())
    assert not knowledge.loaded_from_cache
    assert not config.index_path.exists()


def test_force_rebuild_requires_persistence(config):
    with pytest.raises(ValueError, match="use_cache"):
        builder.build_knowledge_base(config, FakeEmbedder(), force_rebuild=True)


def test_missing_source_is_not_silently_hidden_by_cached_index(config):
    builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True)
    (config.documents_dir / "vpn.txt").unlink()
    with pytest.raises(FileNotFoundError):
        builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True)


def test_files_changed_during_embedding_do_not_replace_previous_index(config):
    builder.build_knowledge_base(config, FakeEmbedder(), use_cache=True)
    original = config.index_path.read_bytes()
    class ChangingEmbedder(FakeEmbedder):
        def embed_chunks(self, chunks):
            (config.documents_dir / "vpn.txt").write_text("生成过程中发生修改。", encoding="utf-8")
            return super().embed_chunks(chunks)
    with pytest.raises(ValueError, match="changed during indexing"):
        builder.build_knowledge_base(config, ChangingEmbedder(), use_cache=True, force_rebuild=True)
    assert config.index_path.read_bytes() == original


def test_index_path_cannot_overwrite_a_source(config):
    with pytest.raises(ValueError, match="overwrite"):
        replace(config, index_path=config.documents_dir / "vpn.txt")
