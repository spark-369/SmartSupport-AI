"""NumPy retrieval math tests (pure, no DB)."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.retrieval import (
    ProductIndex,
    normalize_rows,
    normalize_vector,
    top_k_indices,
)


def test_normalize_rows_unit_length():
    matrix = np.asarray([[3.0, 4.0], [0.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    normalized = normalize_rows(matrix)
    norms = np.linalg.norm(normalized, axis=1)
    assert norms[0] == pytest.approx(1.0, abs=1e-6)
    assert norms[1] == 0.0  # zero row stays zero, never NaN
    assert norms[2] == pytest.approx(1.0, abs=1e-6)


def test_normalize_vector():
    vec = normalize_vector([3.0, 4.0])
    assert float(np.linalg.norm(vec)) == pytest.approx(1.0, abs=1e-6)


def test_top_k_indices_ordering():
    scores = np.asarray([0.1, 0.9, 0.5, 0.7])
    assert top_k_indices(scores, 2) == [1, 3]
    assert top_k_indices(scores, 10) == [1, 3, 2, 0]
    assert top_k_indices(scores, 0) == []


def test_product_index_search_respects_min_score():
    matrix = normalize_rows(np.asarray([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]]))
    index = ProductIndex(
        chunk_ids=["c1", "c2", "c3"],
        contents=["one", "two", "three"],
        doc_names=["m.md"] * 3,
        pages=[1, 2, None],
        chunk_indexes=[0, 1, 2],
        matrix=matrix,
    )
    query = normalize_vector([1.0, 0.05])
    results = index.search(query, top_k=3, min_score=0.5)
    assert [r.chunk_id for r in results] == ["c1", "c3"]  # c2 (orthogonal) filtered
    assert results[0].score > results[1].score
    assert results[1].page is None


def test_product_index_search_top_k_limit():
    matrix = normalize_rows(np.eye(5, dtype=np.float32))
    index = ProductIndex(
        chunk_ids=[f"c{i}" for i in range(5)],
        contents=["x"] * 5,
        doc_names=["m.md"] * 5,
        pages=[None] * 5,
        chunk_indexes=list(range(5)),
        matrix=matrix,
    )
    results = index.search(normalize_vector([1.0, 0, 0, 0, 0]), top_k=2, min_score=0.0)
    assert len(results) == 2
    assert results[0].chunk_id == "c0"
