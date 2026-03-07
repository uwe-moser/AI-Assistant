from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import base64
import logging

import gradio as gr
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from config import DB_PATH
from session_manager import SessionManager
from sidekick import Sidekick
from ui_components import CAPABILITIES_HTML, build_header_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

session_manager = SessionManager()

# Load logo with graceful fallback
try:
    with open("ApexFlow.png", "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
except FileNotFoundError:
    logger.warning("ApexFlow.png not found — header will render without logo")
    _logo_b64 = None


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


async def _new_sidekick(session_id: str, old_sidekick=None) -> Sidekick:
    """Free old resources and create a fresh Sidekick for *session_id*."""
    _free_resources(old_sidekick)
    sidekick = Sidekick(session_id=session_id)
    await sidekick.setup()
    return sidekick


async def initial_setup():
    session_id = session_manager.get_or_create_latest()
    sidekick = await _new_sidekick(session_id)
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
    sidekick = await _new_sidekick(session_id, old_sidekick)
    history = get_history_for_session(session_id)
    session_info = session_manager.get_session(session_id)
    session_name = session_info["name"] if session_info else ""
    return sidekick, session_id, history, session_name


async def create_new_session(old_sidekick):
    session_id = session_manager.create_session()
    sidekick = await _new_sidekick(session_id, old_sidekick)
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
    sidekick = await _new_sidekick(session_id, old_sidekick)
    return "", "", [], sidekick


def _free_resources(sidekick):
    try:
        if sidekick:
            sidekick.cleanup()
    except Exception:
        logger.exception("Exception during cleanup")


# ---------------------------------------------------------------------------
# UI layout
# ---------------------------------------------------------------------------

with gr.Blocks(title="ApexFlow", theme=gr.themes.Default(primary_hue="purple")) as ui:
    gr.HTML(build_header_html(_logo_b64))
    gr.HTML(CAPABILITIES_HTML)

    # State
    sidekick = gr.State(delete_callback=_free_resources)
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
                    placeholder="Rename session...",
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


if __name__ == "__main__":
    ui.launch(inbrowser=True)
