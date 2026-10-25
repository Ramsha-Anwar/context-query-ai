import gradio as gr
from app.main import app as fastapi_app

# Create a dummy UI so Gradio has something to launch
demo = gr.Interface(
    fn=lambda x: "ContextQuery API is running",
    inputs="text",
    outputs="text",
    title="ContextQuery AI Backend"
)

# Mount the FastAPI app directly onto the Gradio app's server
demo.app.mount("/", fastapi_app)