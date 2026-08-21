class FakeVectorStore:
    def __init__(self):
        self.query_calls = []

    def search_similar_cvs(self, job_text, n_results=10, where=None):
        self.query_calls.append(
            {"job_text": job_text, "n_results": n_results, "where": where}
        )
        return {"ids": [[]], "distances": [[]]}
