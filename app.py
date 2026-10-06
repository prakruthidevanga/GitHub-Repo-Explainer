from __future__ import annotations

import os
import threading
import time

import requests
import streamlit as st
import uvicorn

from backend.main import app as fastapi_app
from core.cloud_llm import DEFAULT_HF_MODEL, generate_cloud_explanation
from core.repo_processor import build_code_context, prepare_repository

st.set_page_config(page_title="CodeLens AI", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --ink:#0b1220; --muted:#667085; --line:#e7eaf0; --panel:#ffffff; --accent:#6d5dfc; --accent2:#16c7a3; }
.stApp { background: radial-gradient(circle at 10% 0%, #eef2ff 0, transparent 28%), radial-gradient(circle at 100% 10%, #e7fff8 0, transparent 24%), #f7f8fc; color:var(--ink); }
.block-container { max-width:1240px; padding:1.5rem 2rem 4rem; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b1020 0%,#121936 100%); border-right:1px solid rgba(255,255,255,.08); }
[data-testid="stSidebar"] * { color:#edf2ff !important; }
[data-testid="stSidebar"] .stCaption { color:#aab5d1 !important; }
.hero { position:relative; overflow:hidden; padding:38px 42px; border-radius:28px; background:linear-gradient(135deg,#0b1020 0%,#20285b 54%,#4c3bbf 100%); box-shadow:0 22px 60px rgba(20,28,70,.18); color:white; margin-bottom:22px; }
.hero:after { content:""; position:absolute; width:260px; height:260px; right:-90px; top:-100px; border-radius:50%; background:rgba(255,255,255,.10); filter:blur(2px); }
.kicker { font-size:12px; letter-spacing:.16em; text-transform:uppercase; font-weight:800; color:#b9b2ff; }
.hero h1 { margin:9px 0 10px; font-size:44px; line-height:1.02; color:#fff; letter-spacing:-.035em; }
.hero p { max-width:880px; color:#dce3f7; font-size:16px; line-height:1.7; margin:0; }
.pill { display:inline-flex; margin-top:18px; padding:7px 12px; border-radius:999px; background:rgba(255,255,255,.11); border:1px solid rgba(255,255,255,.16); color:#fff; font-size:12px; font-weight:700; }
.section { font-size:21px; font-weight:800; margin:20px 0 8px; letter-spacing:-.02em; }
.sub { color:var(--muted); font-size:14px; line-height:1.65; }
.metric { background:rgba(255,255,255,.88); border:1px solid var(--line); border-radius:17px; padding:16px 18px; box-shadow:0 8px 28px rgba(15,23,42,.05); min-height:86px; }
.metric .label { color:#7a8496; text-transform:uppercase; letter-spacing:.08em; font-size:10px; font-weight:800; }
.metric .value { color:#101828; font-size:22px; font-weight:850; margin-top:5px; }
.result { background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:20px; padding:26px 30px; box-shadow:0 10px 32px rgba(15,23,42,.06); }
.result h2 { color:#111827; margin-top:10px; }
.result h3 { color:#313b54; }
.flow { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:15px 0 20px; }
.flow span { background:#eef0ff; color:#4338ca; border:1px solid #dedfff; border-radius:999px; padding:7px 11px; font-size:12px; font-weight:750; }
.flow b { color:#9aa2b1; }
.stButton > button { border-radius:12px; min-height:48px; font-weight:800; border:0; }
[data-testid="stTextInput"] input { border-radius:12px; min-height:46px; }
[data-baseweb="tab-list"] { gap:6px; }
[data-baseweb="tab"] { border-radius:10px; }
.footer { text-align:center; color:#8992a3; font-size:12px; padding:30px 0 0; }
.cloud-note { background:#eefbf7; border:1px solid #c8f0e4; color:#146b5b; border-radius:14px; padding:12px 14px; font-size:13px; line-height:1.55; }
</style>
""", unsafe_allow_html=True)

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BACKEND_URL = os.getenv("BACKEND_URL", f"http://{BACKEND_HOST}:{BACKEND_PORT}")


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


@st.cache_resource
def start_backend():
    try:
        if requests.get(f"{BACKEND_URL}/health", timeout=1).ok:
            return True
    except requests.RequestException:
        pass
    if os.getenv("BACKEND_URL"):
        return False
    config = uvicorn.Config(fastapi_app, host=BACKEND_HOST, port=BACKEND_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            if requests.get(f"{BACKEND_URL}/health", timeout=1).ok:
                return True
        except requests.RequestException:
            time.sleep(.1)
    return False


@st.cache_data(ttl=1800, show_spinner=False)
def local_analysis(url: str, model: str, ollama_url: str):
    response = requests.post(
        f"{BACKEND_URL}/explain",
        json={"github_url": url, "model": model, "ollama_url": ollama_url},
        timeout=900,
    )
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(detail)
    return response.json()


@st.cache_data(ttl=1800, show_spinner=False)
def cloud_analysis(url: str, token: str):
    data = prepare_repository(url, full_scan=True)
    result = generate_cloud_explanation(
        data.name,
        build_code_context(data),
        token=token,
        model=None,
        manifest=data.manifest,
        documentation=data.documentation,
        files=data.files,
    )
    return {
        "repository": data.name,
        "github_url": data.url,
        "explanation": result,
        "files_analyzed": len(data.files),
        "total_candidate_files": data.total_candidate_files,
        "context_characters": data.total_chars,
        "context_truncated": data.truncated,
        "language_hints": data.language_hints,
        "manifest": data.manifest,
    }


mode_options = ["☁️ Streamlit Cloud — Hugging Face", "🏠 Local — Ollama"]
with st.sidebar:
    st.markdown("# 🧠 CodeLens AI")
    st.caption("GitHub Repository Intelligence")
    st.divider()
    st.markdown("**Deployment mode**")
    mode = st.radio("Runtime", mode_options, index=0, label_visibility="collapsed")

    if mode.startswith("☁️"):
        st.info("🤖 Auto-select is ON: CodeLens AI checks your Hugging Face account for a live chat model/provider and routes to the fastest available option.")
        st.caption("No HF_MODEL setting is required. Every supported repository file is inspected in batches before the final report is generated.")
        st.markdown('<div class="cloud-note"><b>Cloud mode:</b> no Ollama installation is required on Streamlit Community Cloud.</div>', unsafe_allow_html=True)
    else:
        ollama_url = st.text_input("Ollama URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        model = st.selectbox("Local model", ["qwen2.5:1.5b", "qwen2.5:3b"], index=0)
        st.caption("1.5B = faster • 3B = richer reasoning")

    if mode.startswith("🏠"):
        start_backend()

    st.divider()
    st.markdown("**Pipeline**")
    if mode.startswith("☁️"):
        st.caption("GitHub → GitPython → Code intelligence → Hugging Face → Streamlit")
    else:
        st.caption("GitHub → GitPython → Code intelligence → FastAPI → Ollama → Streamlit")
    st.divider()
    st.markdown("**Coverage**")
    st.caption("Source files • notebooks • configs • architecture • flow • algorithms • interfaces • features")

st.markdown("""
<div class="hero">
  <div class="kicker">GENAI • REPOSITORY INTELLIGENCE</div>
  <h1>Understand any GitHub repository.</h1>
  <p>CodeLens AI turns implementation code into a clear technical briefing, a natural 1–2 minute presentation script, and a structured repository report — with local Ollama mode or cloud inference for Streamlit Community Cloud.</p>
  <span class="pill">● REPOSITORY-AWARE • EVIDENCE-BASED • NO HARDCODED EXPLANATION</span>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section">Analyze a repository</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Paste a public GitHub URL. CodeLens clones it temporarily, inventories the repository, prioritizes implementation code and notebook cells, then generates one complete evidence-based report.</div>', unsafe_allow_html=True)

url = st.text_input("Repository URL", placeholder="https://github.com/username/repository", label_visibility="collapsed")
col_a, col_b = st.columns([4, 1])
with col_a:
    analyze = st.button("✨  Analyze & Generate Explanation", type="primary", use_container_width=True)
with col_b:
    if st.button("Clear cached result", use_container_width=True):
        local_analysis.clear()
        cloud_analysis.clear()
        st.rerun()

if analyze:
    if not url.strip():
        st.error("Please enter a public GitHub repository URL.")
    else:
        with st.status("Building repository intelligence…", expanded=True) as status:
            st.write("Cloning repository")
            st.write("Scanning source, notebooks, configuration and documentation")
            st.write("Preparing focused context for the selected model")
            try:
                if mode.startswith("☁️"):
                    token = _secret("HF_TOKEN")
                    if not token:
                        raise RuntimeError("Add HF_TOKEN in Streamlit Community Cloud → App → Settings → Secrets, then redeploy/re-run the app.")
                    data = cloud_analysis(url.strip(), token)
                else:
                    data = local_analysis(url.strip(), model.strip(), ollama_url.strip())
                status.update(label="Repository explanation ready", state="complete", expanded=False)
            except Exception as exc:
                status.update(label="Analysis failed", state="error", expanded=True)
                st.error(str(exc))
                data = None

        if data:
            inference_label = "Hugging Face Cloud" if mode.startswith("☁️") else "Local Ollama"
            st.success(f"Analyzed {data['repository']} successfully.")
            if data["context_truncated"]:
                st.info("Large file detected: CodeLens keeps the file in the full repository scan and sends it to the LLM in chunks, rather than silently dropping the rest of the file.")

            cols = st.columns(5)
            metric_data = [
                ("Files inspected", f"{data['files_analyzed']}/{data['total_candidate_files']}"),
                ("Code context", f"{data['context_characters']:,}"),
                ("Languages", str(len(data.get('language_hints', [])))),
                ("Model", data["explanation"].get("model", "")),
                ("Inference", inference_label),
            ]
            for col, (label, value) in zip(cols, metric_data):
                col.markdown(f'<div class="metric"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)

            st.markdown('<div class="flow"><span>GitHub</span><b>→</b><span>Clone</span><b>→</b><span>Code intelligence</span><b>→</b><span>LLM</span><b>→</b><span>Explanation</span></div>', unsafe_allow_html=True)

            sections = data["explanation"].get("sections", {})
            tabs = st.tabs(["🎤 1–2 Minute Script", "🧩 Full Repository Report", "📁 Files & Coverage"])
            with tabs[0]:
                st.markdown('<div class="result">', unsafe_allow_html=True)
                st.markdown(sections.get("1–2 Minute Explanation", data["explanation"].get("presentation", "")))
                st.markdown('</div>', unsafe_allow_html=True)
            with tabs[1]:
                st.markdown('<div class="result">', unsafe_allow_html=True)
                st.markdown(data["explanation"].get("full_report", ""))
                st.markdown('</div>', unsafe_allow_html=True)
            with tabs[2]:
                st.markdown('<div class="result">', unsafe_allow_html=True)
                st.markdown("### Repository coverage")
                st.write(f"The analyzer discovered **{data['total_candidate_files']}** supported source/configuration files and sent **all {data['files_analyzed']}** to the cloud inspection stage in batches/chunks.")
                if data.get("language_hints"):
                    st.markdown("**Detected:** " + " · ".join(data["language_hints"]))
                st.markdown("The model is instructed to distinguish between files that were inspected and files that were only inventoried, so it does not invent details about unseen code.")
                st.markdown("### Complete supported-file inventory")
                st.code(data.get("manifest", "No inventory available."), language="text")
                st.markdown('</div>', unsafe_allow_html=True)

            report = data["explanation"].get("full_report", "")
            st.download_button("⬇ Download generated report", data=report, file_name=f"{data['repository']}_CodeLens_Report.md", mime="text/markdown")

st.markdown('<div class="footer">CodeLens AI • GitPython • Hugging Face / Ollama • Streamlit • Repository-aware explanation</div>', unsafe_allow_html=True)
