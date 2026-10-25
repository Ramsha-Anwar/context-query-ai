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

# Mount FastAPI
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

# Start the server manually so FastAPI routes work.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)