import streamlit as st
import requests
import os
from dotenv import load_dotenv
import uuid
import time

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# PAGE CONFIG — must be absolute first Streamlit call
st.set_page_config(
    page_title="NexaBot",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# ──────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────
def _load_users():
    users = {}
    i = 1
    while True:
        u = os.getenv(f"USER{i}_USERNAME")
        p = os.getenv(f"USER{i}_PASSWORD")
        if not u or not p:
            break
        users[u] = p
        i += 1
    return users if users else {"admin": "admin123"}

VALID_USERS = _load_users()

def check_login(username, password):
    return VALID_USERS.get(username) == password

# ──────────────────────────────────────────────────────────────────
# CSS — injected in small separate chunks so Streamlit never
#        treats the content as plain text
# ──────────────────────────────────────────────────────────────────
def inject_css():
    # fonts
    st.markdown(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700'
        '&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )

    # tokens + reset
    st.markdown("""<style>
:root{
  --bg:#060E1E;--surf:#0B1628;--panel:#0F1E35;
  --bdr:#1C2E4A;--bdr2:#243B58;
  --gold:#C9A84C;--gold2:#DDB96A;--gold3:#EED08A;
  --txt:#D4DDED;--muted:#7D92AE;
  --green:#22C67D;--red:#E05555;
  --ff:'Outfit',system-ui,sans-serif;
  --fd:'Cormorant Garamond',Georgia,serif;
  --r:10px;--rl:14px;
  --sh:0 4px 24px rgba(0,0,0,.45);
}
#MainMenu,footer,header,[data-testid="stToolbar"],
[data-testid="stDecoration"],.stDeployButton{display:none!important}
html,body,.stApp{
  font-family:var(--ff)!important;
  background:var(--bg)!important;
  color:var(--txt)!important;
}
.block-container{padding:20px 28px 36px!important;max-width:100%!important}
</style>""", unsafe_allow_html=True)

    # sidebar
    st.markdown("""<style>
[data-testid="stSidebar"]{
  background:var(--surf)!important;
  border-right:1px solid var(--bdr)!important;
}
[data-testid="stSidebar"] *{font-family:var(--ff)!important;color:var(--txt)!important}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3{
  font-family:var(--fd)!important;color:var(--gold2)!important;
  font-size:13px!important;letter-spacing:.1em!important;
  text-transform:uppercase!important;margin:18px 0 6px!important;
}
[data-testid="stSidebar"] hr{border-color:var(--bdr)!important;margin:10px 0!important}
[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;color:var(--txt)!important;
  border:1px solid var(--bdr)!important;border-radius:7px!important;
  font-family:var(--ff)!important;font-size:13px!important;font-weight:500!important;
  padding:9px 14px!important;width:100%!important;text-align:left!important;
  transition:all .18s ease!important;margin-bottom:4px!important;
}
[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(201,168,76,.08)!important;
  border-color:var(--gold)!important;color:var(--gold2)!important;
}
[data-testid="stSidebar"] [data-testid="stMetricValue"]{
  font-family:var(--fd)!important;font-size:26px!important;color:var(--gold2)!important;
}
[data-testid="stSidebar"] [data-testid="stMetricLabel"]{
  font-size:10px!important;text-transform:uppercase!important;
  letter-spacing:.08em!important;color:var(--muted)!important;
}
[data-testid="stSidebar"] .stAlert{
  background:rgba(201,168,76,.06)!important;
  border:1px solid rgba(201,168,76,.2)!important;border-radius:7px!important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] .stCaption p{color:var(--muted)!important;font-size:11px!important}
</style>""", unsafe_allow_html=True)

    # inputs
    st.markdown("""<style>
.stTextInput>div>div>input,
.stTextArea>div>div>textarea{
  background:var(--panel)!important;border:1.5px solid var(--bdr2)!important;
  border-radius:8px!important;color:var(--txt)!important;
  font-family:var(--ff)!important;font-size:14px!important;
  padding:12px 16px!important;
}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus{
  border-color:var(--gold)!important;
  box-shadow:0 0 0 3px rgba(201,168,76,.10)!important;outline:none!important;
}
.stTextInput>div>div>input::placeholder,
.stTextArea>div>div>textarea::placeholder{color:var(--muted)!important}
.stTextInput label,.stTextArea label{
  color:var(--muted)!important;font-size:11px!important;font-weight:600!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;
}
.stNumberInput>div>div>input{
  background:var(--panel)!important;border:1.5px solid var(--bdr2)!important;
  border-radius:8px!important;color:var(--txt)!important;
  font-family:var(--ff)!important;font-size:14px!important;padding:11px 14px!important;
}
.stNumberInput label{
  color:var(--muted)!important;font-size:11px!important;font-weight:600!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;
}
.stSelectbox>div>div{
  background:var(--panel)!important;border:1.5px solid var(--bdr2)!important;
  border-radius:8px!important;color:var(--txt)!important;
  font-family:var(--ff)!important;font-size:14px!important;
}
.stSelectbox label{
  color:var(--muted)!important;font-size:11px!important;font-weight:600!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;
}
</style>""", unsafe_allow_html=True)

    # buttons + expander + alerts
    st.markdown("""<style>
.stButton>button,.stFormSubmitButton>button{
  background:var(--panel)!important;color:var(--gold2)!important;
  border:1px solid rgba(201,168,76,.35)!important;border-radius:8px!important;
  font-family:var(--ff)!important;font-size:12px!important;font-weight:600!important;
  padding:11px 20px!important;letter-spacing:.06em!important;
  text-transform:uppercase!important;transition:all .18s ease!important;
  box-shadow:none!important;
}
.stButton>button:hover,.stFormSubmitButton>button:hover{
  background:rgba(201,168,76,.12)!important;
  border-color:var(--gold)!important;color:var(--gold3)!important;
  transform:translateY(-1px)!important;
}
.streamlit-expanderHeader{
  background:var(--panel)!important;border:1px solid var(--bdr)!important;
  border-radius:8px!important;font-family:var(--ff)!important;
  font-size:13px!important;font-weight:600!important;color:var(--txt)!important;
  padding:12px 16px!important;
}
.streamlit-expanderContent{
  background:var(--panel)!important;border:1px solid var(--bdr)!important;
  border-top:none!important;border-radius:0 0 8px 8px!important;padding:14px!important;
}
.stSuccess{background:rgba(34,198,125,.07)!important;border:1px solid rgba(34,198,125,.25)!important;border-radius:7px!important;font-family:var(--ff)!important;font-size:13px!important}
.stError  {background:rgba(224,85,85,.07)!important; border:1px solid rgba(224,85,85,.22)!important; border-radius:7px!important;font-family:var(--ff)!important;font-size:13px!important}
.stInfo   {background:rgba(96,165,250,.06)!important;border:1px solid rgba(96,165,250,.2)!important; border-radius:7px!important;font-family:var(--ff)!important;font-size:13px!important}
.stWarning{background:rgba(201,168,76,.07)!important;border:1px solid rgba(201,168,76,.22)!important;border-radius:7px!important;font-family:var(--ff)!important;font-size:13px!important}
[data-testid="stMetricValue"]{font-family:var(--fd)!important;font-size:26px!important;font-weight:600!important;color:var(--gold2)!important}
[data-testid="stMetricLabel"]{font-family:var(--ff)!important;font-size:10px!important;font-weight:600!important;color:var(--muted)!important;text-transform:uppercase!important;letter-spacing:.08em!important}
.stSpinner>div{border-top-color:var(--gold)!important}
.stCaption,.stCaption p{font-family:var(--ff)!important;font-size:12px!important;color:var(--muted)!important}
.stCheckbox label span{font-family:var(--ff)!important;font-size:13px!important;color:var(--txt)!important}
[data-testid="stFileUploadDropzone"]{background:var(--panel)!important;border:1.5px dashed var(--bdr2)!important;border-radius:8px!important}
hr{border-color:var(--bdr)!important;margin:14px 0!important}
</style>""", unsafe_allow_html=True)

    # component classes
    st.markdown("""<style>
.nexabar{
  background:var(--surf);border:1px solid var(--bdr);border-radius:var(--rl);
  padding:16px 24px;display:flex;align-items:center;
  justify-content:space-between;margin-bottom:6px;box-shadow:var(--sh);
}
.nexabar-brand{display:flex;align-items:center;gap:14px}
.nexabar-logo{
  width:42px;height:42px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,var(--gold),var(--gold2));
  display:flex;align-items:center;justify-content:center;
  font-family:var(--fd);font-size:18px;font-weight:700;color:var(--bg);
}
.nexabar-title{font-family:var(--fd);font-size:24px;font-weight:700;color:#fff;letter-spacing:-.3px;line-height:1.1}
.nexabar-sub{font-size:10px;font-weight:400;color:var(--muted);letter-spacing:.14em;text-transform:uppercase;margin-top:2px}
.nexabar-right{display:flex;align-items:center;gap:10px}
.pill{border-radius:20px;padding:5px 14px;font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
.pill-user{background:rgba(201,168,76,.10);border:1px solid rgba(201,168,76,.28);color:var(--gold2)}
.pill-live{background:rgba(34,198,125,.10);border:1px solid rgba(34,198,125,.28);color:#6EE7B7;display:flex;align-items:center;gap:6px}
.pill-ok {background:rgba(34,198,125,.08);border:1px solid rgba(34,198,125,.22);color:#22C67D}
.pill-err{background:rgba(224,85,85,.08); border:1px solid rgba(224,85,85,.22); color:var(--red)}
.live-dot{width:7px;height:7px;border-radius:50%;background:#34D399;display:inline-block;animation:blink 2.4s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.gold-rule{height:1px;background:linear-gradient(90deg,var(--gold),transparent);border-radius:1px;margin:0 0 18px}
.sec-hdr{font-family:var(--fd);font-size:22px;font-weight:600;color:#fff;margin-bottom:16px;letter-spacing:-.2px}
.sec-label{font-size:10px;font-weight:700;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}
.docstrip{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--rl);padding:14px 20px 12px;margin-bottom:18px}
.docstrip-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.docstrip-title{font-family:var(--fd);font-size:15px;font-weight:600;color:#fff}
.qabar{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 18px 10px;margin-bottom:14px}
.chat-hdr-bar{background:var(--panel);border:1px solid var(--bdr);border-radius:var(--rl) var(--rl) 0 0;padding:13px 22px;display:flex;align-items:center;justify-content:space-between}
.chat-hdr-title{font-size:11px;font-weight:700;color:var(--muted);letter-spacing:.12em;text-transform:uppercase}
.msg-badge{background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.28);color:var(--gold2);font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px}
.msg-user{display:flex;justify-content:flex-end;margin-bottom:10px}
.msg-bot {display:flex;justify-content:flex-start;align-items:flex-end;gap:10px;margin-bottom:10px}
.msg-avatar{width:34px;height:34px;border-radius:50%;background:var(--panel);border:2px solid var(--gold);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-family:var(--fd);font-size:11px;font-weight:700;color:var(--gold2)}
.bub-user{background:var(--panel);color:var(--txt);padding:11px 16px;border-radius:16px 16px 4px 16px;max-width:60%;font-size:14px;line-height:1.6;border:1px solid var(--bdr2)}
.bub-bot {background:var(--surf);color:var(--txt);padding:13px 18px;border-radius:4px 16px 16px 16px;max-width:72%;font-size:14px;line-height:1.75;border:1px solid var(--bdr);border-left:3px solid var(--gold)}
.bub-bot b,.bub-bot strong{color:#fff;font-weight:600}
.input-wrap{background:var(--surf);border:1px solid var(--bdr);border-radius:0 0 var(--rl) var(--rl);padding:14px 18px}
.prod-card{background:var(--surf);border:1px solid var(--bdr);border-radius:var(--r);padding:16px 18px;margin-bottom:10px}
.prod-cat{font-size:10px;font-weight:700;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;margin-bottom:5px}
.prod-name{font-family:var(--fd);font-size:16px;font-weight:600;color:#fff;margin-bottom:4px}
.prod-price{font-family:var(--fd);font-size:20px;font-weight:700;color:var(--gold);margin-top:6px}
.prod-desc{font-size:12px;color:var(--muted);margin-top:5px;line-height:1.5}
.stk-ok{color:var(--green);font-size:11px;font-weight:700}
.stk-no{color:var(--red);  font-size:11px;font-weight:700}
.form-sec{font-family:var(--fd);font-size:17px;font-weight:600;color:var(--gold2);margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--bdr)}
</style>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────────────────────────
def show_login():
    inject_css()

    st.markdown("""<style>
.login-logo-ring{
  width:64px;height:64px;border-radius:16px;
  background:linear-gradient(135deg,var(--gold),var(--gold2));
  display:flex;align-items:center;justify-content:center;
  font-family:var(--fd);font-size:26px;font-weight:700;color:var(--bg);
  margin:0 auto 18px;
}
.login-title{
  font-family:var(--fd);font-size:34px;font-weight:700;
  color:#fff;text-align:center;margin-bottom:4px;
}
.login-subtitle{
  font-size:11px;font-weight:400;color:var(--muted);
  text-align:center;letter-spacing:.14em;text-transform:uppercase;margin-bottom:28px;
}
.login-divider{
  height:1px;
  background:linear-gradient(90deg,transparent,rgba(201,168,76,.45),transparent);
  margin-bottom:28px;
}
.login-hint{
  text-align:center;margin-top:14px;
  font-size:11px;color:var(--muted);letter-spacing:.04em;
}
</style>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("""
        <div class="login-logo-ring">NX</div>
        <div class="login-title">NexaBot</div>
        <div class="login-subtitle">AI Product Intelligence Platform</div>
        <div class="login-divider"></div>
        """, unsafe_allow_html=True)

        if st.session_state.get("login_error"):
            st.error("Invalid username or password. Please try again.")

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", placeholder="Enter your password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        st.markdown('<div class="login-hint">Default credentials: admin / admin123</div>',
                    unsafe_allow_html=True)

    if submitted:
        if check_login(username.strip(), password):
            st.session_state["authenticated"] = True
            st.session_state["current_user"]  = username.strip()
            st.session_state.pop("login_error", None)
            st.rerun()
        else:
            st.session_state["login_error"] = True
            st.rerun()


if not st.session_state.get("authenticated", False):
    show_login()
    st.stop()

# ──────────────────────────────────────────────────────────────────
# AUTHENTICATED — inject CSS
# ──────────────────────────────────────────────────────────────────
inject_css()

# ──────────────────────────────────────────────────────────────────
# SESSION DEFAULTS
# ──────────────────────────────────────────────────────────────────
_defaults = {
    "session_id":    str(uuid.uuid4()),
    "messages": [{
        "role":    "assistant",
        "content": (
            "Welcome to <strong>NexaBot</strong> - your AI-powered product assistant.<br><br>"
            "I can help you explore products, check pricing, and place orders.<br><br>"
            "Try: <strong>Show all products</strong> or <strong>How do I place an order?</strong>"
        ),
    }],
    "active_tab":    "chat",
    "order_cart":    [],
    "confirm_clear": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────────────────────────
# API HELPER
# ──────────────────────────────────────────────────────────────────
def api(method, path, **kw):
    try:
        r = getattr(requests, method)(
            f"{BACKEND_URL}{path}",
            timeout=kw.pop("timeout", 30),
            **kw,
        )
        return r
    except Exception:
        return None


def send_message(text):
    if not text.strip():
        return
    st.session_state.messages.append({"role": "user", "content": text})
    r = api("post", "/api/query/ask",
            json={"question": text, "top_k": 5},
            headers={"X-Session-ID": st.session_state.session_id})
    if r and r.status_code == 200:
        d = r.json()
        st.session_state.messages.append({
            "role": "assistant",
            "content": d["answer"],
            "products": d.get("related_products", []),
        })
    else:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Could not process your request. {'Backend offline.' if not r else r.text}",
        })

# ──────────────────────────────────────────────────────────────────
# TOP BAR
# ──────────────────────────────────────────────────────────────────
current_user = st.session_state.get("current_user", "User")
r_health     = api("get", "/health", timeout=2)
connected    = bool(r_health and r_health.status_code == 200)
conn_cls     = "pill pill-ok"  if connected else "pill pill-err"
conn_txt     = "Connected"     if connected else "Offline"

st.markdown(f"""
<div class="nexabar">
  <div class="nexabar-brand">
    <div class="nexabar-logo">NX</div>
    <div>
      <div class="nexabar-title">NexaBot</div>
      <div class="nexabar-sub">AI-Powered Product Intelligence Platform</div>
    </div>
  </div>
  <div class="nexabar-right">
    <span class="{conn_cls}">{conn_txt}</span>
    <span class="pill pill-user">{current_user}</span>
    <span class="pill pill-live"><span class="live-dot"></span>Live</span>
  </div>
</div>
<div class="gold-rule"></div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## NexaBot")
    st.caption(f"Signed in as **{current_user}**")

    if st.button("Sign Out", use_container_width=True, key="btn_logout"):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("## Dashboard")
    r_stats = api("get", "/api/upload/stats", timeout=2)
    if r_stats and r_stats.status_code == 200:
        s = r_stats.json()
        c1, c2 = st.columns(2)
        c1.metric("Products", s.get("total_products", 0))
        c2.metric("Docs",     s.get("uploaded_files", 0))
        st.metric("Chunks",   s.get("total_documents", 0))
    else:
        st.info("Start the backend to see stats.")

    st.markdown("---")
    st.markdown("## Navigation")
    for label, key in [("Chat", "chat"), ("Products", "products"),
                       ("Place Order", "order"), ("Orders", "orders")]:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.active_tab = key
            st.rerun()

    st.markdown("---")
    st.markdown("## Controls")
    if st.button("New Conversation", use_container_width=True, key="btn_new"):
        st.session_state.messages   = [{"role": "assistant",
                                         "content": "Session reset. How may I assist you today?"}]
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    if not st.session_state.confirm_clear:
        if st.button("Clear All Documents", use_container_width=True, key="btn_clr"):
            st.session_state.confirm_clear = True
            st.rerun()
    else:
        st.warning("This will delete ALL documents and products.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Confirm", key="clr_yes"):
                r = api("delete", "/api/upload/clear")
                st.success("Cleared!" if r and r.status_code == 200 else "Failed.")
                st.session_state.confirm_clear = False
                time.sleep(1); st.rerun()
        with cc2:
            if st.button("Cancel", key="clr_no"):
                st.session_state.confirm_clear = False
                st.rerun()

    st.markdown("---")
    st.markdown("## Quick Ask")
    for q in ["Show all products", "Delivery policy", "Payment methods", "Pricing info"]:
        if st.button(q, key=f"sq_{q}", use_container_width=True):
            st.session_state.active_tab = "chat"
            send_message(q)
            st.rerun()

    st.markdown("---")
    st.markdown("## Support")
    st.info("support@store.com\n\n0300-1234567\n\nMon - Sat  9AM - 6PM")
    st.caption("NexaBot v2.0")

# ──────────────────────────────────────────────────────────────────
# DOCUMENT MANAGEMENT STRIP
# ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="docstrip">
  <div class="docstrip-top">
    <span class="docstrip-title">Document Management</span>
    <span class="pill {conn_cls}">{conn_txt}</span>
  </div>
</div>
""", unsafe_allow_html=True)

def _upload_files(files, doc_type, label):
    if files:
        st.caption(f"{len(files)} file(s) selected")
        if st.button(f"Upload {label}", key=f"up_{doc_type}", use_container_width=True):
            with st.spinner("Processing..."):
                r = api("post", "/api/upload/documents",
                        files=[("files", (f.name, f, f.type)) for f in files],
                        data={"document_type": doc_type}, timeout=120)
            if r and r.status_code == 200:
                d = r.json()
                st.success(f"Done - {d.get('products_extracted', 0)} products extracted.")
                time.sleep(1); st.rerun()
            else:
                st.error(f"Upload failed: {r.text if r else 'Backend offline'}")

u1, u2, u3 = st.columns(3, gap="medium")
with u1:
    with st.expander("Product Catalog"):
        st.caption("Upload product specs, pricing sheets, catalogs")
        pf = st.file_uploader("pf_up", type=["pdf","txt","csv","json","xlsx","xls","doc","docx"],
                               accept_multiple_files=True, key="pu", label_visibility="collapsed")
        _upload_files(pf, "products", "Products")

with u2:
    with st.expander("Business Rules"):
        st.caption("Upload upsell rules, discount policies")
        rf = st.file_uploader("rf_up", type=["pdf","txt","json","doc","docx"],
                               accept_multiple_files=True, key="ru", label_visibility="collapsed")
        _upload_files(rf, "business_rules", "Rules")

with u3:
    with st.expander("Business Details"):
        st.caption("Upload company info, contact details, policies")
        bf = st.file_uploader("bf_up", type=["pdf","txt","json","doc","docx"],
                               accept_multiple_files=True, key="bu", label_visibility="collapsed")
        _upload_files(bf, "company_info", "Business Info")

# ══════════════════════════════════════════════════════════════════
# TAB: CHAT
# ══════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "chat":

    # Quick actions
    st.markdown('<div class="qabar"><div class="sec-label">Quick Actions</div>', unsafe_allow_html=True)
    qc = st.columns(5)
    for (col, key, lbl, msg) in [
        (qc[0], "qa1", "All Products",   "Show all products"),
        (qc[1], "qa2", "How to Order",   "How do I place an order?"),
        (qc[2], "qa3", "Delivery",        "What is your delivery policy?"),
        (qc[3], "qa4", "Payment Methods", "What payment methods do you accept?"),
        (qc[4], "qa5", "Pricing",         "Tell me about pricing"),
    ]:
        with col:
            if st.button(lbl, use_container_width=True, key=key):
                send_message(msg); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Chat header
    n_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
    st.markdown(f"""
    <div class="chat-hdr-bar">
      <span class="chat-hdr-title">NexaBot - Conversation</span>
      <span class="msg-badge">{n_msgs} message{"s" if n_msgs != 1 else ""}</span>
    </div>
    """, unsafe_allow_html=True)

    # Messages
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(
                f'<div class="msg-user"><div class="bub-user">{msg["content"]}</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="msg-bot">'
                f'<div class="msg-avatar">NX</div>'
                f'<div class="bub-bot">{msg["content"]}</div>'
                f'</div>',
                unsafe_allow_html=True)
            prods = msg.get("products", [])
            if prods:
                with st.expander(f"Related Products ({len(prods)})"):
                    for p in prods[:6]:
                        pc1, pc2, pc3 = st.columns([5, 2, 2])
                        with pc1:
                            st.markdown(f"**{p['name']}**")
                            if p.get("description"):
                                st.caption(p["description"][:90])
                        with pc2:
                            if p.get("price"):
                                st.metric("Price", f"Rs {p['price']:,.0f}")
                        with pc3:
                            st.write("")
                            if st.button("Order", key=f"o_{idx}_{p['name']}", use_container_width=True):
                                st.session_state.order_cart = [{
                                    "product_name": p["name"], "quantity": 1,
                                    "unit_price": p.get("price"),
                                    "product_category": p.get("category"),
                                }]
                                st.session_state.active_tab = "order"
                                st.rerun()

    # Input
    st.markdown('<div class="input-wrap">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        ci1, ci2 = st.columns([6, 1])
        with ci1:
            user_input = st.text_input(
                "msg", label_visibility="collapsed",
                placeholder="Ask NexaBot anything - products, pricing, orders, delivery...")
        with ci2:
            send_btn = st.form_submit_button("Send", use_container_width=True)
        if send_btn and user_input.strip():
            send_message(user_input.strip()); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TAB: PRODUCTS
# ══════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "products":
    st.markdown('<div class="sec-hdr">Product Catalog</div>', unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    with f1:
        search_q = st.text_input("Search", placeholder="Search by name...", key="ps")
    with f2:
        r_cats   = api("get", "/api/products/categories", timeout=5)
        cats     = ["All"] + ([c["name"] for c in r_cats.json().get("categories",[])]
                               if r_cats and r_cats.status_code == 200 else [])
        sel_cat  = st.selectbox("Category", cats, key="pc")
    with f3:
        in_stock = st.checkbox("In Stock Only", key="pstk")
    with f4:
        st.write("")
        st.button("Refresh", use_container_width=True, key="pref")

    if search_q and len(search_q.strip()) >= 2:
        params = {"q": search_q, "limit": 50}
        if sel_cat != "All": params["category"] = sel_cat
        r_p = api("get", "/api/products/search", params=params, timeout=10)
        prods = r_p.json().get("results", []) if r_p and r_p.status_code == 200 else []
    else:
        params = {"limit": 100, "offset": 0}
        if sel_cat != "All":  params["category"]     = sel_cat
        if in_stock:           params["in_stock_only"] = "true"
        r_p = api("get", "/api/products/list", params=params, timeout=10)
        prods = r_p.json().get("products", []) if r_p and r_p.status_code == 200 else []

    if not prods:
        st.info("No products found. Upload a product catalog to get started.")
    else:
        st.caption(f"Showing {len(prods)} product(s)")
        for i in range(0, len(prods), 3):
            cols = st.columns(3, gap="medium")
            for j, col in enumerate(cols):
                if i + j >= len(prods):
                    break
                p = prods[i + j]
                with col:
                    sc  = "stk-ok" if p.get("in_stock", True) else "stk-no"
                    st_ = "In Stock" if p.get("in_stock", True) else "Out of Stock"
                    pr  = f'<div class="prod-price">Rs {p["price"]:,.0f}</div>' if p.get("price") else ""
                    st.markdown(f"""
                    <div class="prod-card">
                      <div class="prod-cat">{p.get('category') or 'General'}</div>
                      <div class="prod-name">{p['name']}</div>
                      <div class="{sc}">{st_}</div>
                      {pr}
                      <div class="prod-desc">{(p.get('description') or '')[:90]}</div>
                    </div>""", unsafe_allow_html=True)
                    if p.get("colors"):
                        st.caption("Colors: " + ", ".join(p["colors"][:4]))
                    if st.button("Order This", key=f"pord_{i}_{j}", use_container_width=True):
                        st.session_state.order_cart = [{
                            "product_name": p["name"], "quantity": 1,
                            "unit_price": p.get("price"), "product_category": p.get("category"),
                        }]
                        st.session_state.active_tab = "order"
                        st.rerun()

# ══════════════════════════════════════════════════════════════════
# TAB: PLACE ORDER
# ══════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "order":
    st.markdown('<div class="sec-hdr">Place an Order</div>', unsafe_allow_html=True)

    cart      = st.session_state.order_cart
    def_name  = cart[0]["product_name"]              if cart else ""
    def_price = float(cart[0].get("unit_price") or 0.0) if cart else 0.0

    with st.form("order_form"):
        st.markdown('<div class="form-sec">Customer Information</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            full_name  = st.text_input("Full Name *",    placeholder="Full name")
            phone      = st.text_input("Phone Number *", placeholder="03XX-XXXXXXX")
            email      = st.text_input("Email",          placeholder="email@example.com")
        with c2:
            address    = st.text_input("Address",        placeholder="Street address")
            city       = st.text_input("City",           placeholder="e.g. Karachi")
            postal     = st.text_input("Postal Code",    placeholder="e.g. 75500")

        st.markdown('<div class="form-sec">Order Items</div>', unsafe_allow_html=True)
        i1, i2, i3 = st.columns([4, 1, 2])
        with i1: prod_name  = st.text_input("Product Name *", value=def_name, placeholder="Product name")
        with i2: qty        = st.number_input("Qty", min_value=1, max_value=999, value=1)
        with i3: unit_price = st.number_input("Unit Price (Rs)", min_value=0.0, value=def_price, step=100.0)

        i4, i5 = st.columns(2)
        with i4: color = st.text_input("Color / Variant",  placeholder="e.g. Black, XL")
        with i5: specs = st.text_input("Specifications",   placeholder="Special requirements")

        st.markdown('<div class="form-sec">Payment and Delivery</div>', unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1: pay_method  = st.selectbox("Payment Method", ["COD","Bank Transfer","JazzCash","EasyPaisa"])
        with p2: del_date    = st.text_input("Preferred Delivery Date", placeholder="YYYY-MM-DD")
        del_notes = st.text_area("Delivery Instructions", placeholder="Special delivery notes...", height=80)

        sub = st.form_submit_button("Place Order", use_container_width=True)

    if sub:
        if not full_name.strip() or not phone.strip() or not prod_name.strip():
            st.error("Please fill in Full Name, Phone, and Product Name.")
        else:
            payload = {
                "customer_info": {
                    "full_name": full_name.strip(), "phone": phone.strip(),
                    "email": email.strip() or None,   "address": address.strip() or None,
                    "city": city.strip() or None,      "postal_code": postal.strip() or None,
                },
                "items": [{
                    "product_name": prod_name.strip(), "quantity": qty,
                    "unit_price":   unit_price if unit_price > 0 else None,
                    "total_price":  unit_price * qty if unit_price > 0 else None,
                    "color":        color.strip() or None,
                    "specifications": specs.strip() or None,
                }],
                "payment_details":       {"method": pay_method},
                "delivery_instructions": del_notes.strip() or None,
                "preferred_delivery_date": del_date.strip() or None,
            }
            with st.spinner("Placing order..."):
                r = api("post", "/api/orders/place", json=payload)
            if r and r.status_code == 200:
                d = r.json()
                if d.get("success"):
                    st.success(f"Order placed successfully! ID: **{d.get('order_id')}**")
                    st.info(f"Estimated delivery: {d.get('estimated_delivery', 'N/A')}")
                    st.session_state.order_cart = []
                else:
                    st.error(d.get("message", "Order failed."))
            else:
                st.error(f"Failed to place order: {r.text if r else 'Backend offline'}")

# ══════════════════════════════════════════════════════════════════
# TAB: ORDERS DASHBOARD
# ══════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "orders":
    st.markdown('<div class="sec-hdr">Orders Dashboard</div>', unsafe_allow_html=True)

    r_os = api("get", "/api/orders/statistics", timeout=5)
    if r_os and r_os.status_code == 200:
        os_ = r_os.json().get("statistics", {})
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders", os_.get("total_orders", 0))
        m2.metric("Pending",      os_.get("pending",      0))
        m3.metric("Delivered",    os_.get("delivered",    0))
        rev = os_.get("total_revenue", 0)
        m4.metric("Revenue", f"Rs {rev:,.0f}" if rev else "N/A")
    else:
        st.info("No order statistics available yet.")

    st.markdown("---")
    st.markdown('<div class="form-sec">Look Up an Order</div>', unsafe_allow_html=True)
    with st.form("order_lookup"):
        lc1, lc2 = st.columns([4, 1])
        with lc1:
            oid_in = st.text_input("oid", placeholder="e.g. ORD-20260409120000-ABCD1234",
                                   label_visibility="collapsed")
        with lc2:
            lbtn = st.form_submit_button("Search", use_container_width=True)
        if lbtn and oid_in.strip():
            r_o = api("get", f"/api/orders/{oid_in.strip()}")
            if r_o and r_o.status_code == 200:
                st.json(r_o.json().get("order", {}))
            elif r_o and r_o.status_code == 404:
                st.error("Order not found.")
            else:
                st.error("Could not fetch order.")

    st.markdown("---")
    st.markdown('<div class="form-sec">Update Order Status</div>', unsafe_allow_html=True)
    with st.form("status_update"):
        sc1, sc2, sc3 = st.columns([3, 2, 1])
        with sc1: upd_oid  = st.text_input("oid2", placeholder="ORD-...", label_visibility="collapsed")
        with sc2: new_stat = st.selectbox("stat", ["pending","processing","shipped","delivered","cancelled"],
                                          label_visibility="collapsed")
        with sc3: ubtn = st.form_submit_button("Update", use_container_width=True)
        if ubtn and upd_oid.strip():
            r_u = api("put", f"/api/orders/status/{upd_oid.strip()}", params={"status": new_stat})
            if r_u and r_u.status_code == 200:
                st.success(f"Order {upd_oid} updated to '{new_stat}'.")
            else:
                st.error(f"Update failed: {r_u.text if r_u else 'Backend offline'}")

    st.markdown("---")
    st.markdown('<div class="form-sec">Export Orders</div>', unsafe_allow_html=True)
    ec1, ec2, ec3 = st.columns(3)
    with ec1: sd = st.text_input("Start Date", placeholder="YYYY-MM-DD", key="exp_s")
    with ec2: ed = st.text_input("End Date",   placeholder="YYYY-MM-DD", key="exp_e")
    with ec3:
        st.write("")
        if st.button("Export to Excel", use_container_width=True, key="exp_btn"):
            params = {}
            if sd.strip(): params["start_date"] = sd.strip()
            if ed.strip(): params["end_date"]   = ed.strip()
            r_ex = api("get", "/api/orders/export", params=params, timeout=30)
            if r_ex and r_ex.status_code == 200:
                st.success(f"Exported to: `{r_ex.json().get('file_path','')}`")
            else:
                st.error("Export failed.")