"""The reference library: what is always in the prompt, and what is searched."""

from __future__ import annotations

from citychat.knowledge import KnowledgeBase, tokenize


def test_tokenize_drops_stopwords_and_single_characters():
    assert tokenize("What is the proximity time of a city?") == ["proximity", "time", "city"]


def test_core_documents_are_loaded_and_small_enough_to_keep_in_the_prompt(context):
    kb: KnowledgeBase = context.knowledge
    assert len(kb.core) >= 3
    text = kb.core_text()
    # Roughly 3-6k tokens: big enough to cache, small enough to send every turn.
    assert 4_000 < len(text) < 40_000
    for phrase in ("proximity time", "15-minute", "population", "Gini"):
        assert phrase.lower() in text.lower()


def test_the_paper_is_indexed_in_searchable_chunks(context):
    kb: KnowledgeBase = context.knowledge
    assert kb.documents()
    assert len(kb.chunks) > 20
    # No chunk may be so big that returning it floods the context.
    assert max(len(c.text) for c in kb.chunks) <= 1_500


def test_search_finds_the_methodology_passage(context):
    hits = context.knowledge.search("20 nearest POIs average time per category")
    assert hits
    assert any("20 nearest" in hit["text"] or "20 closest" in hit["text"] for hit in hits)
    assert hits[0]["relevance"] > 0
    assert hits[0]["source"]


def test_search_finds_published_per_city_figures(context):
    hits = context.knowledge.search("POIs per 1000 people needed Atlanta Milan")
    assert any("Atlanta" in hit["text"] for hit in hits)


def test_search_results_are_ranked(context):
    hits = context.knowledge.search("Gini index inequality of accessibility", limit=4)
    scores = [hit["relevance"] for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_search_for_nonsense_returns_nothing(context):
    assert context.knowledge.search("zzzqqq flurbulous") == []


def test_search_respects_the_limit(context):
    assert len(context.knowledge.search("city", limit=2)) <= 2
