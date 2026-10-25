import gradio as gr
from app.main import app as fastapi_app

# Create a simple dummy UI for the root URL
def health_check(name):
    return f"Hello {name}! The ContextQuery API is running. Use the /api/v1/ endpoints."

demo = gr.Interface(
    fn=health_check,
    inputs="text",
    outputs="text",
    title="ContextQuery AI Backend",
    description="This is the backend API for ContextQuery AI."
)

# Mount your FastAPI app at the root, and put the Gradio UI at /ui
app = gr.mount_gradio_app(fastapi_app, demo, path="/ui")