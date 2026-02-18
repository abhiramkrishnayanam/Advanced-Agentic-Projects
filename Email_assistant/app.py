import streamlit as st
import json
from langgraph.types import Command
from agent import (
    agent_graph,
    load_memory,
    save_memory,
    across_thread_memory,
    AgentState,
)

st.set_page_config(page_title="Email Assistant", page_icon="✉️")

# Custom CSS to center-align the title and keep it in one row
st.markdown(
    """
    <style>
    h1 {
        white-space: nowrap;   /* keep text in one line */
        overflow: visible;     /* show full text */
        text-overflow: clip;   /* no ellipsis */
        text-align: center;    /* center align */
        margin-bottom: 30px;   /* add space below title */
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📧 AI Query & Email Support Assistant")

# Load memory at startup
load_memory(across_thread_memory, user_id="me")

# --- CONFIG: which nodes need explicit human approval ---
APPROVAL_REQUIRED_NODES = {"delete_email_node", "send_email_node"}

# Session state setup
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_response" not in st.session_state:
    st.session_state.last_response = None
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None


# ---------- helpers ----------
def safe_get(obj, key, default=None):
    """Return obj[key] if dict-like, else getattr(obj, key), else default."""
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default

def normalize_response(raw_response, message_fallback=None):
    def pick(*keys, default=None):
        for k in keys:
            v = safe_get(raw_response, k)
            if v not in (None, "", []):
                return v
        return default

    message_val = pick("message", "msg", default=message_fallback or "✅ Action completed successfully!")

    return {
        "next_node": safe_get(raw_response, "next_node"),
        "count": safe_get(raw_response, "count"),
        "summary": pick("summary", "summ", default=None),
        "reply": safe_get(raw_response, "reply"),   # <-- only reply
        "answers": safe_get(raw_response, "answers"),  # <-- KB answers always here
        "deleted": safe_get(raw_response, "deleted"),
        "message": message_val,
    }


def render_assistant_entry(assistant):
    """Return a one-line user-friendly string for the assistant entry."""

    # 0) KB answers
    if assistant.get("answers"):
        a = assistant["answers"]
        if isinstance(a, (list, tuple)):
            return "📚 " + "\n\n".join(str(x) for x in a)
        if isinstance(a, dict):
            return "📚 " + json.dumps(a, indent=2)
        return f"📚 {a}"

    # 1) Analytics (count)
    if assistant.get("count") is not None:
        return f"📊 Emails today: {assistant.get('count')}"

    # 2) QA / Replies
    if assistant.get("reply"):
        r = assistant.get("reply")
        if isinstance(r, (list, tuple)):
            return "🤖 " + "\n\n".join(str(x) for x in r)
        if isinstance(r, dict):
            return "🤖 " + json.dumps(r, indent=2)
        return f"🤖 {r}"

    # 3) Summary
    if assistant.get("summary"):
        return f"📝 Summary: {assistant.get('summary')}"

    # 4) Approval-required nodes
    next_node = assistant.get("next_node")
    if next_node in APPROVAL_REQUIRED_NODES:
        if next_node == "delete_email_node":
            return "🗑️ Email deleted successfully!"
        if next_node == "send_email_node":
            return "📧 Email sent successfully!"

    # 5) fallback
    return assistant.get("message", "✅ Action completed successfully!")

# --- User input ---
user_input = st.text_input("Enter your email command or query:")

if user_input:
    state = AgentState(query=user_input)

    # Run the graph
    response = agent_graph.invoke(
        state,
        config={"configurable": {"thread_id": "1", "user_id": "me"}}
    )

    # DEBUG - remove after verification
    try:
        st.write("DEBUG raw response:", response)
    except Exception:
        pass

    # Check for interruptions from the graph
    if "__interrupt__" in response:
        # Graph is requesting human approval / input
        interrupt_data = response["__interrupt__"][0].value
        st.session_state.pending_action = interrupt_data

        # Build a cleaned assistant_entry representing pending state
        assistant_entry = {
            "next_node": safe_get(response, "next_node"),
            "count": safe_get(response, "count"),
            "summary": safe_get(response, "summary"),
            "reply": safe_get(response, "answers"),
            "deleted": safe_get(response, "deleted"),
            "query_dlt": safe_get(response, "query_dlt"),
            "message": interrupt_data.get("question", safe_get(response, "message", "⚠️ Pending action.")),
            "__interrupt__": True,
            "raw_interrupt": interrupt_data,
        }

        st.session_state.last_response = assistant_entry
        st.session_state.chat_history.append({
            "user": user_input,
            "assistant": assistant_entry
        })

        st.warning(interrupt_data["question"])
    else:
        # Normal path — normalize into a plain dict
        message_to_show = safe_get(response, "message", "✅ Action completed successfully!")
        assistant_entry = normalize_response(response, message_fallback=message_to_show)

        st.session_state.pending_action = None
        st.session_state.last_response = assistant_entry
        st.session_state.chat_history.append({
            "user": user_input,
            "assistant": assistant_entry
        })

# --- HUMAN-IN-THE-LOOP APPROVAL ---
if st.session_state.pending_action:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve"):
            resumed = agent_graph.invoke(
                Command(resume="yes"),
                config={"configurable": {"thread_id": "1", "user_id": "me"}}
            )
            # normalize resumed into assistant_entry before storing
            resumed_entry = normalize_response(resumed, message_fallback="✅ Approved and executed.")
            st.success("✅ Approved and executed.")
            st.session_state.chat_history.append({
                "user": "yes",
                "assistant": resumed_entry
            })
            st.session_state.last_response = resumed_entry
            st.session_state.pending_action = None
            

    with col2:
        if st.button("❌ Cancel"):
            resumed = agent_graph.invoke(
                Command(resume="no"),
                config={"configurable": {"thread_id": "1", "user_id": "me"}}
            )
            cancelled_entry = normalize_response(resumed, message_fallback="❌ Cancelled.")
            st.info("❌ Cancelled.")
            st.session_state.chat_history.append({
                "user": "no",
                "assistant": cancelled_entry
            })
            st.session_state.pending_action = None
            st.session_state.last_response = cancelled_entry


# --- DISPLAY: show only the most recent result (clean) ---
if not st.session_state.pending_action and st.session_state.chat_history:
    chat = st.session_state.chat_history[-1]   # latest only
    st.markdown(f"**You:** {chat['user']}")
    entry = chat["assistant"]

    next_node = entry.get("next_node")
    query_dlt = entry.get("query_dlt")
    deleted = entry.get("deleted")

    # --- Error handling first ---
    if isinstance(query_dlt, str) and "⚠️ no recipient email-id found" in query_dlt.lower():
        st.error(query_dlt)

    elif isinstance(deleted, dict) and deleted.get("status") == "not_found" and (
        next_node == "delete_email_node" or "delete" in (entry.get("message","") or "").lower()
    ):
        st.error("⚠️ No matching email found for deletion.")

    else:
        # --- Priority 1: Knowledge base answers ---
        if entry.get("reply") or entry.get("answers"):
            pretty = render_assistant_entry(entry)
            
            # Check if the assistant reply indicates human support needed
            if isinstance(entry.get("reply"), str) and "❓ this query requires human support" in entry["reply"].lower():
                # make sure flagged list exists
                if "flagged" not in st.session_state:
                    st.session_state.flagged = []
                # add flagged query + reply
                st.session_state.flagged.append({
                    "user_query": chat["user"],
                    "assistant_reply": entry["reply"]
                })
            
            st.success(pretty)

        # --- Priority 2: Email deletion results ---
        elif isinstance(deleted, dict) and deleted.get("status") == "success":
            st.success("🗑️ Email deleted successfully!")

        elif isinstance(deleted, dict) and deleted.get("status") == "error":
            st.error(f"❌ Delete failed: {deleted.get('message','Unknown error')}")

        # --- Always show structured email summary if present ---
        if entry.get("summary"):
            st.markdown("### 📝 Email Summary")
            if isinstance(entry["summary"], dict):
                summary_obj = entry["summary"]
                st.write("**Status:**", summary_obj.get("status", ""))
                st.write("**Sender:**", summary_obj.get("sender", ""))
                st.write("**Recipient:**", summary_obj.get("recipient", ""))
                with st.expander("Full summary"):
                    st.write(summary_obj.get("summary", ""))
            else:
                st.info(entry["summary"])
                
        # --- Priority 4: Email count ---
        elif entry.get("count") is not None:
            st.success(f"📊 Emails today: {entry['count']}")

        # --- Fallback: plain message ---
        else:
            pretty = render_assistant_entry(entry)
            st.info(pretty)

else:
    if st.session_state.pending_action:
        st.write("Waiting for your approval to proceed (Approve / Cancel).")
    else:
        st.write("Enter a command to run (e.g., 'count emails today').")
        
if __name__ == "__main__":
    save_memory(across_thread_memory, user_id="me")
