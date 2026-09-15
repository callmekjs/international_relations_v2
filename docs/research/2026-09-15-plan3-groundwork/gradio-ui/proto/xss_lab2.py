"""Dataframe with the default "str" datatype: is a hostile cell shown as text? (127.0.0.1:7864)"""
import gradio as gr

P = ('<img src="http://127.0.0.1:7999/df-str-img.png" onerror="window.__xss_dfstr=1"> '
     '![m](http://127.0.0.1:7999/df-str-md.png) **bold**')

with gr.Blocks() as demo:
    b = gr.Button("fill", elem_id="fill")
    df = gr.Dataframe(elem_id="c-dfstr", headers=["항목", "내용"], datatype=["str", "str"], interactive=False, wrap=True)
    b.click(lambda: [["a", P]], None, df)

demo.launch(server_name="127.0.0.1", server_port=7864, footer_links=[], enable_monitoring=False, run_history=False,
            ssr_mode=False)
