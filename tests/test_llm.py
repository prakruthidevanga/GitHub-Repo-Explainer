from core import llm


def test_complete_report_is_generated(monkeypatch):
    calls = []
    headings = [
        "1–2 Minute Explanation", "Project Overview", "Main Technologies",
        "Architecture & How It Works", "Data / Execution Flow", "Important Files & Code Roles",
        "Key Features", "Models, Algorithms & Logic", "Inputs, Outputs & Interfaces",
        "Dependencies & Configuration", "Limitations & Future Improvements",
    ]
    def fake_call(prompt, model, base_url, max_tokens=1100):
        calls.append(prompt)
        return "\n\n".join(f"## {h}\nUseful evidence-based explanation for {h}." for h in headings) + "\n" + ("More detail. " * 30)
    monkeypatch.setattr(llm, "_call", fake_call)
    result = llm.generate_explanation("demo", "===== FILE: app.py =====\nprint('hello')", "test", "http://test")
    assert set(result) == {"model", "full_report", "sections", "presentation"}
    assert len(calls) == 1
    assert "Project Overview" in result["full_report"]
    assert "How It Works" in result["full_report"]
    assert "1–2 Minute Explanation" in result["presentation"]
