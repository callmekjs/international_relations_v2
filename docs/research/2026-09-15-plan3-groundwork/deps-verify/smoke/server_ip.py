import sys, json
import gradio as gr
port = int(sys.argv[1]); ssr = sys.argv[2] == "ssr"
def whoami(x, request: gr.Request):
    h = {k: v for k, v in request.headers.items() if k.lower() in ("x-forwarded-for", "x-real-ip", "user-agent", "x-forwarded-host", "x-forwarded-proto", "x-direct-url", "forwarded")}
    return json.dumps({"client_host": request.client.host if request.client else None, "headers": h})
def gen(x, request: gr.Request):
    for i in range(3):
        import time; time.sleep(0.2); yield f"{i} " + (request.headers.get("x-forwarded-for") or "-")
with gr.Blocks() as demo:
    t = gr.Textbox(); o = gr.Textbox()
    gr.Button("w").click(whoami, t, o, api_name="whoami")
    gr.Button("g").click(gen, t, o, api_name="gen")
demo.queue().launch(server_name="127.0.0.1", server_port=port, ssr_mode=ssr)
