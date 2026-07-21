"""ponytail: FAQ path via hybrid RAG pipeline."""

from types import SimpleNamespace

from app.brain.rag.pipeline import faq_chunks


class _FakeSession:
    def exec(self, _stmt):
        return self

    def all(self):
        return [
            SimpleNamespace(id=1, question="How does shop credit work?", answer="Credit is udhaar with a limit."),
            SimpleNamespace(id=2, question="Minimum order quantity", answer="MOQ is shown on each product."),
        ]


def main() -> None:
    hits = faq_chunks(_FakeSession(), "tell me about shop credit and udhaar")
    assert hits and "udhaar" in hits[0]["text"].lower(), hits
    miss = faq_chunks(_FakeSession(), "zzzz unrelated")
    assert not miss, miss
    print("chatbot_faq_check ok")


if __name__ == "__main__":
    main()
