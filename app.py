import base64
import os
import shutil
import gradio as gr
from sidekick import Sidekick
from session_manager import SessionManager
from scheduler import _list_tasks, _remove_task, TaskRunner
from knowledge import KnowledgeBase
from config import DB_PATH
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


ui.launch(inbrowser=True)