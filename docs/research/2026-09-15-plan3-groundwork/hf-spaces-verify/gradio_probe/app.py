import json, os
import gradio as gr

def who(request: gr.Request):
    return json.dumps({
        "client_host": request.client.host,
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "user_agent": request.headers.get("user-agent"),
    })

with gr.Blocks() as demo:
    b = gr.Button("who")
    o = gr.Textbox()
    b.click(who, None, o, api_name="who")

if __name__ == "__main__":
    print("cfg default_concurrency_limit env:", os.getenv("GRADIO_DEFAULT_CONCURRENCY_LIMIT"))
    demo.queue()
    print("api_open:", demo.api_open, "max_size:", demo._queue.max_size, "default_concurrency_limit:", demo._queue.default_concurrency_limit)
    demo.launch(server_name="127.0.0.1", server_port=7871, ssr_mode=False)
