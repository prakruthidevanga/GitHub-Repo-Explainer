from core import cloud_llm


def test_discover_hf_model(monkeypatch):
    class Response:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [
                {"id": "random/large", "providers": [{"provider": "x", "status": "live", "throughput": 100}]},
                {"id": "Qwen/Qwen-small-4B", "providers": [{"provider": "y", "status": "live", "is_free": True, "throughput": 80}]},
            ]}
    monkeypatch.setattr(cloud_llm.requests, "get", lambda *a, **k: Response())
    model, routed, providers = cloud_llm.discover_hf_model("hf_test")
    assert model == "Qwen/Qwen-small-4B"
    assert routed == "Qwen/Qwen-small-4B:fastest"
    assert providers == [{"provider": "y", "status": "live"}]


def test_discover_requires_live_provider(monkeypatch):
    class Response:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"id": "google/gemma", "providers": [{"provider": "x", "status": "error"}]}]}
    monkeypatch.setattr(cloud_llm.requests, "get", lambda *a, **k: Response())
    try:
        cloud_llm.discover_hf_model("hf_test")
    except RuntimeError as exc:
        assert "No live Hugging Face" in str(exc)
    else:
        raise AssertionError("Expected a clear no-live-provider error")


def test_cloud_call_and_parser(monkeypatch):
    headings = [
        "1–2 Minute Explanation", "Project Overview", "Main Technologies",
        "Architecture & How It Works", "Data / Execution Flow", "Important Files & Code Roles",
        "Key Features", "Models, Algorithms & Logic", "Inputs, Outputs & Interfaces",
        "Dependencies & Configuration", "Limitations & Future Improvements",
    ]
    answer = "\n\n".join(f"## {h}\nUseful evidence-based explanation for {h}." for h in headings) + "\n" + ("More detail. " * 30)

    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": answer}}]}

    monkeypatch.setattr(cloud_llm.requests, "post", lambda *a, **k: Response())
    result = cloud_llm.generate_cloud_explanation("demo", "app.py", "hf_test", "test/model")
    assert result["model"] == "test/model"
    assert "Project Overview" in result["full_report"]
    assert result["presentation"]
