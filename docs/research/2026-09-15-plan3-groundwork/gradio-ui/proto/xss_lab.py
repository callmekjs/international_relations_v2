"""Which Gradio components sanitize raw model text? Sends the same hostile string, unescaped, to each one.
A flag on window.__xss_* or a request to the local tracker (127.0.0.1:7999) means the payload was live.

    PYTHONUTF8=1 ../venv/Scripts/python.exe xss_lab.py     # http://127.0.0.1:7862"""
import gradio as gr

T = "http://127.0.0.1:7999"


def payload(tag: str) -> str:
    return (f'<b>bold-{tag}</b> <img src="{T}/{tag}-img.png" onerror="window.__xss_{tag}_img=1"> '
            f'<script>window.__xss_{tag}_script=1</script> <a href="javascript:window.__xss_{tag}_js=1" id="a-{tag}">js-link</a> '
            f'<span class="badge b-ok" style="color:red" id="s-{tag}">styled</span> '
            f'![md]({T}/{tag}-md.png) [mdlink](javascript:window.__xss_{tag}_mdjs=1) '
            f'<iframe src="{T}/{tag}-iframe.html"></iframe> <details open><summary>sum-{tag}</summary>x</details> '
            f'${{window.__xss_{tag}_tpl=1}} `${{window.__xss_{tag}_tick=1}}` <svg onload="window.__xss_{tag}_svg=1"></svg>')


def fill():
    return (payload("markdown"), payload("html"), [{"role": "assistant", "content": payload("chatbot")}],
            payload("htmltpl"), [[payload("dataframe")]])


with gr.Blocks(title="xss lab") as demo:
    btn = gr.Button("fill", elem_id="fill")
    md = gr.Markdown(elem_id="c-markdown")
    ht = gr.HTML(elem_id="c-html")
    chat = gr.Chatbot(elem_id="c-chatbot", feedback_options=None)
    tpl = gr.HTML(elem_id="c-htmltpl", html_template="<div class='w'>{{value}}</div>")
    df = gr.Dataframe(elem_id="c-dataframe", headers=["cell"], datatype=["markdown"], interactive=False)
    btn.click(fill, None, [md, ht, chat, tpl, df])
    btn2 = gr.Button("fill2", elem_id="fill2")
    # no quote, backtick or '=' (Handlebars escapes those), so the text survives into the JS template literal
    btn2.click(lambda: ("${Object.assign(window,{__xss_hb_value:1})} hb-test",
                        "${Object.assign(window,{__xss_default_tpl:1})} default-test"), None, [tpl, ht])
    tpl_prop = gr.HTML(elem_id="c-htmlprop", html_template="<div>{{label_text}} ${value}</div>",
                       label_text="${Object.assign(window,{__xss_hb_prop:1})}")

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7862, footer_links=[], enable_monitoring=False,
                run_history=False, ssr_mode=False)
