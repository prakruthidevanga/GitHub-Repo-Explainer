# 🧠 CodeLens AI — Local GitHub Repository Code Explainer

A professional local GenAI mini-project that accepts a public GitHub repository URL, clones it with GitPython, inventories the repository, extracts implementation code (including Jupyter notebook code cells), and asks a locally running Ollama model to generate a detailed repository briefing.

## What the app produces

The local LLM generates:

- A natural **1–2 minute presentation script** (about 220–280 words)
- Project overview and purpose
- Main technologies and libraries
- Architecture and end-to-end execution flow
- Data / control flow
- Important files and code roles
- Key features
- Models, algorithms and logic
- Inputs, outputs and interfaces
- Dependencies and configuration
- Limitations and future improvements

The explanation is **generated from repository evidence**, not hard-coded.

## Important coverage design

The app keeps a repository-wide file inventory so the model knows which supported files exist. It prioritizes actual implementation files and notebook code cells over README content. For large repositories, it sends controlled implementation excerpts plus the inventory and documentation excerpt. The report explicitly distinguishes files inspected in detail from files that were only inventoried.

A model cannot literally read an arbitrarily large repository in one prompt; therefore "complete coverage" is handled honestly through inventory + prioritized code inspection rather than pretending unseen code was analyzed.

## Recommended local model

Fast default:

```text
qwen2.5:1.5b
```

Richer (if your machine can handle it):

```bash
ollama pull qwen2.5:3b
```

Then select `qwen2.5:3b` in the sidebar.

## Run locally

1. Install Ollama.
2. Make sure Ollama is already running. If Ollama Desktop is running, do **not** start a second `ollama serve` process.
3. Pull the model:

```bash
ollama pull qwen2.5:1.5b
```

4. Install Python dependencies:

```bash
pip install -r requirements.txt
```

5. Start Streamlit:

```bash
streamlit run app.py
```

6. Keep the Ollama URL as:

```text
http://localhost:11434
```

## Test repository

```text
https://github.com/prakruthidevanga/MoodPlus-NLP
```

For this notebook-heavy project, the analyzer extracts the notebook's actual code cells instead of treating the README as the implementation.

## Architecture

```text
GitHub URL
   ↓
GitPython clone
   ↓
Repository inventory + source prioritization
   ↓
Notebook code-cell extraction / file excerpts
   ↓
FastAPI
   ↓
Ollama local LLM
   ↓
Structured repository report
   ↓
Streamlit professional UI
```

## Speed optimization

The app uses one focused generation request for the complete report instead of repeatedly sending the entire repository context for separate sections. Streamlit also caches completed analyses for 30 minutes, so analyzing the same repository/model again is much faster. Streamlit's official documentation recommends caching expensive data/API work with `st.cache_data`. citeturn0search0turn0search1

## Streamlit Cloud

The UI can be deployed to Streamlit Community Cloud, but `http://localhost:11434` refers to the Streamlit server itself, not your laptop. A fully local assignment demonstration should run Streamlit and Ollama on the same laptop. A public deployment needs an Ollama-compatible inference service reachable from that deployment; do not expose an unsecured Ollama server to the public internet.

## Requirements checklist

- [x] Python
- [x] GitPython
- [x] Hugging Face not required for Ollama inference; local open-source model is served by Ollama
- [x] FastAPI
- [x] Pydantic
- [x] Uvicorn
- [x] Streamlit
- [x] GitHub URL input
- [x] Repository cloning
- [x] Source/configuration detection
- [x] Jupyter notebook code extraction
- [x] Local LLM-generated explanation
- [x] Beginner-friendly 1–2 minute script
- [x] Detailed technical report
- [x] Professional modern UI
- [x] Large-repository coverage inventory
- [x] Downloadable generated report

## Streamlit Community Cloud deployment

The project supports two modes from the sidebar:

- **Streamlit Cloud — Hugging Face:** intended for public deployment. It clones the public GitHub repository in the Streamlit runtime and sends the prepared repository context to Hugging Face Inference Providers through the OpenAI-compatible chat-completions endpoint.
- **Local — Ollama:** intended for the original local-LLM assignment/demo. It uses Ollama running on the user's computer.

### Deploy to Streamlit Community Cloud

1. Create a GitHub repository containing the contents of this `final_release` folder.
2. In Streamlit Community Cloud, create a new app and select `app.py` as the main file.
3. Deploy the app.
4. Open the app's **Settings → Secrets** and add:

```toml
HF_TOKEN = "hf_your_fine_grained_token"
HF_MODEL = "automatic live-model/provider discovery"
```

The token must have Hugging Face **Inference Providers** permission. Never commit the token to GitHub.

5. Keep the sidebar in **Streamlit Cloud — Hugging Face** mode and paste a public GitHub repository URL.

Hugging Face documents the OpenAI-compatible endpoint at `https://router.huggingface.co/v1/chat/completions` and automatic `:fastest` provider routing. The cloud mode uses that endpoint directly with `requests`.

### Important deployment note

The cloud mode does **not** try to access `localhost:11434`. That address would refer to the Streamlit Cloud runtime itself, not the user's laptop. Ollama therefore remains available only through the Local — Ollama mode.
