import base64
import os
import shutil
import gradio as gr
from sidekick import Sidekick
from session_manager import SessionManager
from scheduler import _list_tasks, _remove_task, TaskRunner
from knowledge import KnowledgeBase
from config import DB_PATH, SANDBOX_DIR
import jobs
import interview
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

session_manager = SessionManager()
task_runner = TaskRunner()

with open("ApexFlow.png", "rb") as _f:
    _logo_b64 = base64.b64encode(_f.read()).decode()


def get_dropdown_choices():
    return [(name, id_) for id_, name, _ in session_manager.list_sessions()]


def get_history_for_session(session_id):
    hist = SQLChatMessageHistory(
        session_id=session_id,
        connection=f"sqlite:///{DB_PATH}",
    )
    result = []
    for msg in hist.messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


async def initial_setup():
    await task_runner.start()
    session_id = session_manager.get_or_create_latest()
    sidekick = Sidekick(session_id=session_id)
    await sidekick.setup()
    history = get_history_for_session(session_id)
    choices = get_dropdown_choices()
    session_info = session_manager.get_session(session_id)
    session_name = session_info["name"] if session_info else ""
    return (
        sidekick,
        session_id,
        history,
        gr.Dropdown(choices=choices, value=session_id),
        session_name,
    )


async def process_message(sidekick, message, success_criteria, history):
    async for updated_history in sidekick.run_superstep(message, success_criteria, history):
        yield updated_history, sidekick, "", load_scheduled_tasks()


async def switch_session(session_id, old_sidekick):
    free_resources(old_sidekick)
    sidekick = Sidekick(session_id=session_id)
    await sidekick.setup()
    history = get_history_for_session(session_id)
    session_info = session_manager.get_session(session_id)
    session_name = session_info["name"] if session_info else ""
    return sidekick, session_id, history, session_name


async def create_new_session(old_sidekick):
    free_resources(old_sidekick)
    session_id = session_manager.create_session()
    sidekick = Sidekick(session_id=session_id)
    await sidekick.setup()
    choices = get_dropdown_choices()
    return (
        sidekick,
        session_id,
        [],
        gr.Dropdown(choices=choices, value=session_id),
        "",
    )


def do_rename_session(session_id, name):
    if name.strip():
        session_manager.rename_session(session_id, name.strip())
    return gr.Dropdown(choices=get_dropdown_choices(), value=session_id)


async def delete_and_switch(session_id, old_sidekick):
    """Delete the current session and switch to another."""
    free_resources(old_sidekick)
    session_manager.delete_session(session_id)

    new_session_id = session_manager.get_or_create_latest()
    sidekick = Sidekick(session_id=new_session_id)
    await sidekick.setup()
    history = get_history_for_session(new_session_id)
    choices = get_dropdown_choices()
    session_info = session_manager.get_session(new_session_id)
    session_name = session_info["name"] if session_info else ""
    return (
        sidekick,
        new_session_id,
        history,
        gr.Dropdown(choices=choices, value=new_session_id),
        session_name,
    )


async def reset(session_id, old_sidekick):
    free_resources(old_sidekick)
    sidekick = Sidekick(session_id=session_id)
    await sidekick.setup()
    return "", "", [], sidekick


def free_resources(sidekick):
    print("Cleaning up")
    try:
        if sidekick:
            sidekick.cleanup()
    except Exception as e:
        print(f"Exception during cleanup: {e}")


def load_scheduled_tasks():
    """Load scheduled tasks into a Dataframe-friendly list of rows."""
    tasks = _list_tasks()
    rows = []
    for t in tasks:
        rows.append([
            t["id"],
            t["description"],
            t["cron_expr"],
            "enabled" if t["enabled"] else "disabled",
            t["last_run"] or "never",
            "yes" if t["notify"] else "no",
        ])
    return rows


def cancel_task_and_refresh(task_id):
    """Cancel a task by ID and return updated table rows."""
    task_id = task_id.strip()
    if task_id:
        _remove_task(task_id)
    return load_scheduled_tasks(), ""


def upload_to_knowledge_base(files):
    """Copy uploaded files to sandbox/knowledge/ and index them."""
    if not files:
        return "No files selected.", load_knowledge_base_docs()

    kb = KnowledgeBase()
    results = []
    for file_path in files:
        filename = os.path.basename(file_path)
        dest = os.path.join("sandbox", "knowledge", filename)
        shutil.copy2(file_path, dest)
        result = kb.add_document(dest)
        results.append(result)

    return "\n".join(results), load_knowledge_base_docs()


def reindex_knowledge_base():
    """Re-index all files in sandbox/knowledge/."""
    kb = KnowledgeBase()
    result = kb.index_all()
    return result, load_knowledge_base_docs()


def load_knowledge_base_docs():
    """Load knowledge base document list for the UI table."""
    kb = KnowledgeBase()
    if kb._collection.count() == 0:
        return []

    all_meta = kb._collection.get()["metadatas"]
    doc_chunks: dict[str, int] = {}
    for meta in all_meta:
        source = meta.get("source", "unknown")
        doc_chunks[source] = doc_chunks.get(source, 0) + 1

    return [[source, str(count)] for source, count in sorted(doc_chunks.items())]


# ── Job search panel helpers ─────────────────────────────────────────────────

def load_jobs_table(status_filter: str = "all"):
    """Return job pipeline rows for the Dataframe."""
    status = None if status_filter == "all" else status_filter
    rows = jobs.list_jobs(status=status, limit=100)
    return [
        [
            j["id"],
            j["status"],
            f"{j['match_score']:.0f}" if j.get("match_score") is not None else "—",
            j["title"] or "",
            j["company"] or "",
            j["location"] or "",
            j["apply_url"] or "",
        ]
        for j in rows
    ]


def load_interview_sessions_table():
    """Return interview session rows for the Dataframe."""
    sessions = interview.list_sessions()
    rows = []
    for s in sessions:
        turns = interview.get_turns(s["id"])
        answered = sum(1 for t in turns if t.get("answer"))
        rows.append([
            s["id"],
            s["status"],
            s.get("title") or "",
            f"{answered}/{len(turns)}",
            f"{s['overall_score']:.0f}" if s.get("overall_score") is not None else "—",
            s.get("created_at", ""),
        ])
    return rows


def upload_application_sources(files):
    """Copy uploaded CV/LinkedIn PDFs to the sandbox root."""
    if not files:
        return "No files selected."
    import shutil as _shutil
    os.makedirs(SANDBOX_DIR, exist_ok=True)
    names = []
    for file_path in files:
        filename = os.path.basename(file_path)
        dest = os.path.join(SANDBOX_DIR, filename)
        _shutil.copy2(file_path, dest)
        names.append(filename)
    return (
        f"Uploaded to {SANDBOX_DIR}/: " + ", ".join(names) +
        ". Now ask the assistant: 'Ingest my CV and LinkedIn profile' "
        "(referencing these filenames)."
    )


def show_profile_summary():
    """Return a concise summary of the stored candidate profile."""
    profile = jobs.get_profile()
    if not profile:
        return "No candidate profile stored yet. Upload a CV + LinkedIn PDF above and ask the assistant to ingest them."
    import json as _json
    lines = [f"Top-level keys: {', '.join(profile.keys())}"]
    if "name" in profile:
        lines.append(f"Name: {profile['name']}")
    if "summary" in profile:
        lines.append(f"Summary: {str(profile['summary'])[:300]}")
    if "experience" in profile and isinstance(profile["experience"], list):
        lines.append(f"Experience entries: {len(profile['experience'])}")
    if "skills" in profile:
        lines.append(f"Skills: {_json.dumps(profile['skills'], ensure_ascii=False)[:300]}")
    return "\n".join(lines)


with gr.Blocks(title="ApexFlow", theme=gr.themes.Default(primary_hue="purple")) as ui:
    gr.HTML(f"""
<div style="display: flex; align-items: center; gap: 24px; margin-bottom: 4px; width: 100%;">
  <img src="data:image/png;base64,{_logo_b64}" style="height: 180px; width: auto; flex-shrink: 0;">
  <div style="flex: 1; min-width: 0;">
    <p class="header-desc" style="margin: 0; font-size: 16px; color: #444; line-height: 1.6;">
      ApexFlow is a multi-agent AI assistant powered by a hierarchical orchestrator architecture.
      An orchestrator delegates tasks to six specialist agents — Research, Browser, Documents, Knowledge, Location, and System — each with its own focused tool set.
      This design enables efficient, evidence-based answers to complex queries by combining real-time web access, sandboxed code execution, document search, and task automation.
    </p>
  </div>
</div>
""")
    gr.HTML("""
<style>
  .agent-card {
    background: #f8f6ff; border: 1px solid #e0d8f0; border-radius: 12px;
    padding: 12px 16px; font-size: 13px; color: #333; line-height: 1.5;
  }
  .agent-card .agent-name {
    font-weight: 700; font-size: 14px; margin-bottom: 4px; color: #5b21b6;
  }
  .agent-card .agent-tools {
    font-size: 12px; color: #666; margin-top: 4px;
  }
  @media (prefers-color-scheme: dark) {
    .agent-card { background: #2d2640; border-color: #4a3d70; color: #e0d8ff; }
    .agent-card .agent-name { color: #c4b8e8; }
    .agent-card .agent-tools { color: #9b8fc0; }
    .cap-section-title { color: #c4b8e8 !important; }
    .header-desc { color: #ccc !important; }
  }
  #reset-btn { background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #fca5a5 !important; }
  #reset-btn:hover { background: #fecaca !important; }
  #new-session-btn, #new-session-btn button { width: fit-content !important; min-width: 0 !important; }
  #rename-btn, #rename-btn button { width: fit-content !important; min-width: 0 !important; }
</style>
<div style="margin-bottom: 12px;">
  <div class="cap-section-title" style="font-weight: 600; font-size: 14px; color: #555; margin-bottom: 8px;">Specialist Agents</div>
  <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">

    <div class="agent-card">
      <div class="agent-name">Research Agent</div>
      Web search, Wikipedia, arXiv papers, YouTube transcripts
      <div class="agent-tools">Tools: Google Search, Wikipedia, arXiv, YouTube Transcript API</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Browser Agent</div>
      Navigate websites, click links, fill forms, extract content
      <div class="agent-tools">Tools: Playwright (Chromium), screenshots, page extraction</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Documents Agent</div>
      File management, PDFs, spreadsheets, charts
      <div class="agent-tools">Tools: File I/O, PDF read/create, CSV/Excel, matplotlib charts</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Knowledge Agent</div>
      Search and manage your personal document collection
      <div class="agent-tools">Tools: ChromaDB semantic search, document indexing</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Location Agent</div>
      Address analysis, nearby amenities, commute times
      <div class="agent-tools">Tools: Google Places, Maps, apartment search</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">System Agent</div>
      Task scheduling, notifications, Python execution
      <div class="agent-tools">Tools: APScheduler, Pushover, Python REPL</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Job Search Agent</div>
      Find jobs, manage CV profile, tailor applications (discover-only)
      <div class="agent-tools">Tools: Adzuna, Serper, ranking, CV/cover-letter tailoring</div>
    </div>

    <div class="agent-card">
      <div class="agent-name">Interview Coach</div>
      Run mock interviews tied to a specific job, score answers
      <div class="agent-tools">Tools: question planning, per-answer scoring, summary</div>
    </div>

  </div>
</div>
""")

    # State
    sidekick = gr.State(delete_callback=free_resources)
    current_session_id = gr.State()

    # Session bar
    with gr.Group():
        with gr.Row():
            gr.Markdown("### Session Management")
        with gr.Row():
            with gr.Column(scale=3):
                session_dropdown = gr.Dropdown(
                    label="Session Overview",
                    choices=[],
                    interactive=True,
                )
                with gr.Row():
                    new_session_btn = gr.Button("+ New Session", variant="primary", elem_id="new-session-btn")
                    delete_session_btn = gr.Button("Delete Session", variant="stop", elem_id="delete-session-btn")
            with gr.Column(scale=3):
                session_name_input = gr.Textbox(
                    label="Current Session",
                    placeholder="Rename session…",
                )
                rename_btn = gr.Button("Rename Session", elem_id="rename-btn")

    # Scheduled Tasks panel
    with gr.Accordion("Scheduled Tasks", open=False):
        scheduled_tasks_table = gr.Dataframe(
            headers=["ID", "Description", "Schedule", "Status", "Last Run", "Notify"],
            datatype=["str", "str", "str", "str", "str", "str"],
            interactive=False,
            label="Background Tasks",
        )
        with gr.Row():
            cancel_task_id = gr.Textbox(label="Task ID to cancel", placeholder="e.g. a1b2c3d4", scale=3)
            cancel_task_btn = gr.Button("Cancel Task", variant="stop", scale=1)
            refresh_tasks_btn = gr.Button("Refresh", variant="secondary", scale=1)

    # Knowledge Base panel
    with gr.Accordion("Knowledge Base", open=False):
        kb_docs_table = gr.Dataframe(
            headers=["Document", "Chunks"],
            datatype=["str", "str"],
            interactive=False,
            label="Indexed Documents",
        )
        with gr.Row():
            kb_upload = gr.File(
                label="Upload documents to knowledge base",
                file_count="multiple",
                file_types=[".pdf", ".txt", ".md", ".csv"],
                scale=3,
            )
        with gr.Row():
            kb_status = gr.Textbox(label="Status", interactive=False, scale=3)
            kb_reindex_btn = gr.Button("Re-index", variant="secondary", scale=1)

    # Job Search panel (discover-only)
    with gr.Accordion("Job Search", open=False):
        gr.Markdown(
            "**Discover-only.** The assistant finds and ranks jobs, and prepares "
            "tailored CVs/cover letters in `sandbox/job_applications/<job_id>/`. "
            "It never submits anything — you click apply manually."
        )
        with gr.Row():
            profile_upload = gr.File(
                label="Upload CV and LinkedIn profile PDFs",
                file_count="multiple",
                file_types=[".pdf"],
                scale=3,
            )
            profile_status = gr.Textbox(label="Upload status", interactive=False, scale=2)
        with gr.Row():
            profile_summary = gr.Textbox(
                label="Current candidate profile",
                interactive=False,
                lines=6,
                scale=3,
            )
            refresh_profile_btn = gr.Button("Refresh profile", variant="secondary", scale=1)

        with gr.Row():
            jobs_status_filter = gr.Dropdown(
                label="Filter by status",
                choices=["all"] + list(jobs.PIPELINE_STATUSES),
                value="all",
                scale=1,
            )
            refresh_jobs_btn = gr.Button("Refresh jobs", variant="secondary", scale=1)
        jobs_table = gr.Dataframe(
            headers=["ID", "Status", "Score", "Title", "Company", "Location", "Apply URL"],
            datatype=["str", "str", "str", "str", "str", "str", "str"],
            interactive=False,
            label="Job pipeline",
            wrap=True,
        )

    # Interview practice panel
    with gr.Accordion("Interview Practice", open=False):
        gr.Markdown(
            "Ask the assistant to **start an interview for job [id]** to begin a "
            "practice session. It runs in the chat above — answers are scored here."
        )
        refresh_interviews_btn = gr.Button("Refresh sessions", variant="secondary")
        interviews_table = gr.Dataframe(
            headers=["Session", "Status", "Title", "Answered", "Overall", "Created"],
            datatype=["str", "str", "str", "str", "str", "str"],
            interactive=False,
            label="Interview sessions",
            wrap=True,
        )

    # Chat
    with gr.Row():
        chatbot = gr.Chatbot(label="ApexFlow", height=400, type="messages")

    # Input area
    with gr.Group():
        with gr.Row():
            message = gr.Textbox(show_label=False, placeholder="Your request to ApexFlow")
        with gr.Row():
            success_criteria = gr.Textbox(
                show_label=False, placeholder="OPTIONAL: What are your success criteria?"
            )
    with gr.Row():
        reset_button = gr.Button("Reset", variant="secondary", elem_id="reset-btn")
        go_button = gr.Button("Go!", variant="primary")

    # ── Event wiring ──────────────────────────────────────────────────────────

    ui.load(
        initial_setup,
        inputs=[],
        outputs=[sidekick, current_session_id, chatbot, session_dropdown, session_name_input],
    )

    session_dropdown.change(
        switch_session,
        inputs=[session_dropdown, sidekick],
        outputs=[sidekick, current_session_id, chatbot, session_name_input],
    )

    new_session_btn.click(
        create_new_session,
        inputs=[sidekick],
        outputs=[sidekick, current_session_id, chatbot, session_dropdown, session_name_input],
    )

    rename_btn.click(
        do_rename_session,
        inputs=[current_session_id, session_name_input],
        outputs=[session_dropdown],
    )

    session_name_input.submit(
        do_rename_session,
        inputs=[current_session_id, session_name_input],
        outputs=[session_dropdown],
    )

    delete_session_btn.click(
        delete_and_switch,
        inputs=[current_session_id, sidekick],
        outputs=[sidekick, current_session_id, chatbot, session_dropdown, session_name_input],
        js="(session_id, sidekick) => { if (!confirm('Delete this session permanently?')) throw new Error('Cancelled'); return [session_id, sidekick]; }",
    )

    message.submit(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message, scheduled_tasks_table],
    )
    success_criteria.submit(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message, scheduled_tasks_table],
    )
    go_button.click(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message, scheduled_tasks_table],
    )
    reset_button.click(
        reset,
        inputs=[current_session_id, sidekick],
        outputs=[message, success_criteria, chatbot, sidekick],
    )

    # Scheduled tasks panel wiring
    ui.load(load_scheduled_tasks, inputs=[], outputs=[scheduled_tasks_table])
    refresh_tasks_btn.click(load_scheduled_tasks, inputs=[], outputs=[scheduled_tasks_table])
    cancel_task_btn.click(
        cancel_task_and_refresh,
        inputs=[cancel_task_id],
        outputs=[scheduled_tasks_table, cancel_task_id],
    )


    # Knowledge base panel wiring
    ui.load(load_knowledge_base_docs, inputs=[], outputs=[kb_docs_table])
    kb_upload.upload(
        upload_to_knowledge_base,
        inputs=[kb_upload],
        outputs=[kb_status, kb_docs_table],
    )
    kb_reindex_btn.click(
        reindex_knowledge_base,
        inputs=[],
        outputs=[kb_status, kb_docs_table],
    )

    # Job search panel wiring
    ui.load(lambda: load_jobs_table("all"), inputs=[], outputs=[jobs_table])
    ui.load(show_profile_summary, inputs=[], outputs=[profile_summary])
    profile_upload.upload(
        upload_application_sources,
        inputs=[profile_upload],
        outputs=[profile_status],
    )
    refresh_profile_btn.click(show_profile_summary, inputs=[], outputs=[profile_summary])
    refresh_jobs_btn.click(load_jobs_table, inputs=[jobs_status_filter], outputs=[jobs_table])
    jobs_status_filter.change(load_jobs_table, inputs=[jobs_status_filter], outputs=[jobs_table])

    # Interview practice panel wiring
    ui.load(load_interview_sessions_table, inputs=[], outputs=[interviews_table])
    refresh_interviews_btn.click(
        load_interview_sessions_table, inputs=[], outputs=[interviews_table]
    )


if __name__ == "__main__":
    ui.launch(inbrowser=True)