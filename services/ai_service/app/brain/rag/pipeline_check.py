"""ponytail: hybrid RAG expand + FAQ merge smoke check."""

from types import SimpleNamespace

from app.brain.rag.pipeline import expand_query, faq_chunks


class _Sess:
    def exec(self, _stmt):
        return self

    def all(self):
        return [
            SimpleNamespace(id=1, question="How does shop credit work?", answer="Udhaar with a limit."),
            SimpleNamespace(id=2, question="Delivery hours", answer="9 AM to 10 PM."),
        ]


def main() -> None:
    assert "credit" in expand_query("what is my udhaar").lower()
    hits = faq_chunks(_Sess(), "shop credit udhaar", k=2)
    assert hits and hits[0]["source"] == "faq"
    assert "Udhaar" in hits[0]["text"]
    print("pipeline_check ok")


if __name__ == "__main__":
    main()
