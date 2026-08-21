# Local application imports
from backend.access_control import Viewer
from src.database.vector_store import VectorStore


class FakeCollection:
    def __init__(self):
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return {"ids": [[]], "distances": [[]]}


def test_search_similar_cvs_scopes_query_to_viewer_visible_metadata():
    store = object.__new__(VectorStore)
    collection = FakeCollection()
    store.cvs_collection = collection

    store.search_similar_cvs("python", viewer=Viewer(user_id="owner"), n_results=2)

    assert collection.queries == [
        {
            "query_texts": ["python"],
            "n_results": 2,
            "where": {
                "$or": [
                    {"owner_user_id": "owner"},
                    {"is_public": True},
                ]
            },
        }
    ]


def test_search_similar_cvs_for_anonymous_viewer_queries_public_only():
    store = object.__new__(VectorStore)
    collection = FakeCollection()
    store.cvs_collection = collection

    store.search_similar_cvs("python", viewer=Viewer(), n_results=2)

    assert collection.queries[0]["where"] == {"is_public": True}


def test_search_similar_cvs_for_admin_does_not_add_visibility_filter():
    store = object.__new__(VectorStore)
    collection = FakeCollection()
    store.cvs_collection = collection

    store.search_similar_cvs("python", viewer=Viewer(is_admin=True), n_results=2)

    assert "where" not in collection.queries[0]


def test_search_similar_cvs_owner_only_filters_before_vector_retrieval():
    store = object.__new__(VectorStore)
    collection = FakeCollection()
    store.cvs_collection = collection

    store.search_similar_cvs(
        "python",
        viewer=Viewer(user_id="demo-owner"),
        n_results=3,
        owner_only=True,
    )

    assert collection.queries == [
        {
            "query_texts": ["python"],
            "n_results": 3,
            "where": {"owner_user_id": "demo-owner"},
        }
    ]


class FakeGetCollection:
    def get(self, **kwargs):
        return {
            "ids": ["public", "private_system", "missing_owner"],
            "documents": ["public", "system", "unknown"],
            "metadatas": [
                {"owner_user_id": "owner", "is_public": True},
                {"owner_user_id": "system", "is_public": False},
                {"is_public": False},
            ],
        }


def test_list_all_cvs_fails_closed_for_private_system_and_missing_owner_metadata():
    store = object.__new__(VectorStore)
    store.cvs_collection = FakeGetCollection()

    cvs = store.list_all_cvs()

    assert [cv["id"] for cv in cvs] == ["public"]
