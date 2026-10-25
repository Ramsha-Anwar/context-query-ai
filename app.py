import gradio as gr
from app.main import app as fastapi_app
import uvicorn

def health_check(name):
    return f"Hello {name}! The ContextQuery API is running."

demo = gr.Interface(
    fn=health_check,
    inputs="text",
    outputs="text",
    title="ContextQuery AI Backend",
    description="This is the backend API for ContextQuery AI."
)

# Mount Gradio into FastAPI
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

# Override the launch method. 
# Hugging Face's runner automatically calls demo.launch(). 
# We replace it with our own function that starts the FastAPI server instead.
def custom_launch(*args, **kwargs):
    uvicorn.run(app, host="0.0.0.0", port=7860)

demo.launch = custom_launch