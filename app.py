import base64
import gradio as gr
from sidekick import Sidekick
from session_manager import SessionManager
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

session_manager = SessionManager()

with open("ApexFlow.png", "rb") as _f:
    _logo_b64 = base64.b64encode(_f.read()).decode()


def get_dropdown_choices():
    return [(name, id_) for id_, name, _ in session_manager.list_sessions()]


def get_history_for_session(session_id):
    hist = SQLChatMessageHistory(
        session_id=session_id,
        connection="sqlite:///sidekick_chat_history.db",
    )
    result = []
    for msg in hist.messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


async def initial_setup():
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
        yield updated_history, sidekick, ""


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


with gr.Blocks(title="ApexFlow", theme=gr.themes.Default(primary_hue="purple")) as ui:
    gr.HTML(f"""
<div style="display: flex; align-items: center; gap: 24px; margin-bottom: 4px; width: 100%;">
  <img src="data:image/png;base64,{_logo_b64}" style="height: 180px; width: auto; flex-shrink: 0;">
  <div style="flex: 1; min-width: 0;">
    <p class="header-desc" style="margin: 0; font-size: 16px; color: #444; line-height: 1.6;">
      Apex Flow is a high-performance information retrieval and processing assistant. It is designed to provide evidence-based answers to complex technical queries by integrating real-time web access, sandboxed code execution, and deep-file indexing into a single conversational interface.
      Rather than relying solely on internal model weights, Apex Flow leverages a suite of specialized tools to verify facts, process local data, and cite academic sources in real-time.
    </p>
  </div>
</div>
""")
    gr.HTML("""
<style>
  .cap-chip {
    background: #f3f0ff; border: 1px solid #d8d0f0; border-radius: 16px;
    padding: 4px 12px; font-size: 13px; cursor: default; position: relative;
    transition: background 0.15s; color: #333;
  }
  .cap-chip:hover { background: #e8e0ff; }
  .cap-chip .cap-tip {
    visibility: hidden; opacity: 0; transition: opacity 0.15s;
    position: absolute; bottom: calc(100% + 6px); left: 0;
    background: #333; color: #fff; padding: 5px 10px; border-radius: 6px;
    font-size: 12px; white-space: nowrap; pointer-events: none; z-index: 10;
  }
  .cap-chip:hover .cap-tip { visibility: visible; opacity: 1; }
  @media (prefers-color-scheme: dark) {
    .cap-chip { background: #2d2640; border-color: #4a3d70; color: #e0d8ff; }
    .cap-chip:hover { background: #3d3360; }
    .cap-cat-label { color: #9b8fc0 !important; }
    .cap-section-title { color: #c4b8e8 !important; }
    .header-desc { color: #ccc !important; }
  }
  #reset-btn { background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #fca5a5 !important; }
  #reset-btn:hover { background: #fecaca !important; }
  #new-session-btn, #new-session-btn button { width: fit-content !important; min-width: 0 !important; }
  #rename-btn, #rename-btn button { width: fit-content !important; min-width: 0 !important; }
</style>
<div style="margin-bottom: 12px;">
  <div class="cap-section-title" style="font-weight: 600; font-size: 14px; color: #555; margin-bottom: 8px;">🛠️ Capabilities</div>
  <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px;">

    <div>
      <div class="cap-cat-label" style="font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Web &amp; Internet</div>
      <div style="display: flex; flex-wrap: wrap; gap: 5px;">
        <span class="cap-chip">🌐 Web Navigation<span class="cap-tip">Browse the internet, navigate to URLs, and extract information from web pages</span></span>
        <span class="cap-chip">🔍 Data Extraction<span class="cap-tip">Extract text and hyperlinks from web pages, search for files in directories</span></span>
        <span class="cap-chip">🎬 YouTube Transcripts<span class="cap-tip">Fetch transcripts from YouTube videos for summarisation and analysis</span></span>
      </div>
    </div>

    <div>
      <div class="cap-cat-label" style="font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Files &amp; Documents</div>
      <div style="display: flex; flex-wrap: wrap; gap: 5px;">
        <span class="cap-chip">📁 File Management<span class="cap-tip">Read, write, move, copy, and delete files on disk</span></span>
        <span class="cap-chip">📄 PDF Reader<span class="cap-tip">Extract and read text content from PDF files</span></span>
        <span class="cap-chip">📝 PDF Creator<span class="cap-tip">Generate proper, openable PDF files with formatted content</span></span>
      </div>
    </div>

    <div>
      <div class="cap-cat-label" style="font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Research</div>
      <div style="display: flex; flex-wrap: wrap; gap: 5px;">
        <span class="cap-chip">📖 Wikipedia<span class="cap-tip">Retrieve information from Wikipedia for general knowledge queries</span></span>
        <span class="cap-chip">🎓 arXiv Search<span class="cap-tip">Search and retrieve academic papers from arXiv</span></span>
      </div>
    </div>

    <div>
      <div class="cap-cat-label" style="font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Utilities</div>
      <div style="display: flex; flex-wrap: wrap; gap: 5px;">
        <span class="cap-chip">🐍 Python Execution<span class="cap-tip">Run Python code to perform calculations or process data</span></span>
        <span class="cap-chip">🔔 Push Notifications<span class="cap-tip">Send push notifications to keep you updated on task progress</span></span>
      </div>
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
                new_session_btn = gr.Button("+ New Session", variant="primary", elem_id="new-session-btn")
            with gr.Column(scale=3):
                session_name_input = gr.Textbox(
                    label="Current Session",
                    placeholder="Rename session…",
                )
                rename_btn = gr.Button("Rename Session", elem_id="rename-btn")

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

    message.submit(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message],
    )
    success_criteria.submit(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message],
    )
    go_button.click(
        process_message,
        inputs=[sidekick, message, success_criteria, chatbot],
        outputs=[chatbot, sidekick, message],
    )
    reset_button.click(
        reset,
        inputs=[current_session_id, sidekick],
        outputs=[message, success_criteria, chatbot, sidekick],
    )


ui.launch(inbrowser=True)