import streamlit as st
import os
import traceback
from dotenv import load_dotenv, set_key
from video_generator import generate_video

# Load environment variables from .env file if present
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_FILE)

st.set_page_config(page_title="AI Video Generator", page_icon="🎥", layout="wide")

st.markdown("<style>.stButton>button { background-color: #ff4b4b; color: white; border-radius: 8px; height: 48px; font-weight: bold; transition: all 0.3s ease; } .stButton>button:hover { background-color: #ff3333; box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4); }</style>", unsafe_allow_html=True)

st.title("🎥 Local AI Video Generator")
st.markdown("Generate short-form videos for social media powered by **Gemini AI** and Free AI Image endpoints.")

# Initialize session state for API key
if "api_key" not in st.session_state:
    st.session_state["api_key"] = os.getenv("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("Settings ⚙️")
    
    api_key_input = st.text_input(
        "Gemini API Key", 
        value=st.session_state["api_key"], 
        type="password", 
        help="Get your free Gemini API Key from Google AI Studio"
    )
    
    st.markdown("[👉 Get your free Gemini API Key here](https://aistudio.google.com/app/apikey)")
    
    col_apply, col_dummy = st.columns([1, 1])
    with col_apply:
        if st.button("Apply API Key 💾", key="btn_apply_api"):
            st.session_state["api_key"] = api_key_input.strip()
            try:
                if not os.path.exists(ENV_FILE):
                    with open(ENV_FILE, "w") as f:
                        f.write(f"GEMINI_API_KEY={st.session_state['api_key']}\n")
                else:
                    set_key(ENV_FILE, "GEMINI_API_KEY", st.session_state["api_key"])
                st.sidebar.success("✅ API Key applied & remembered!")
            except Exception as e:
                st.sidebar.info("✅ API Key applied for session!")
                
    st.divider()
    
    # Default to local outputs directory or Downloads
    default_dl = os.path.join(os.path.dirname(__file__), "outputs")
    output_folder = st.text_input("Download Destination Folder", value=default_dl)

col1, col2 = st.columns([2, 1])

with col1:
    topic = st.text_area(
        "What should the video be about or write your script:", 
        height=200, 
        placeholder="e.g. 5 fascinating facts about space that will blow your mind... OR paste your full script here."
    )
    
with col2:
    aspect_ratio = st.selectbox("Video Format (Aspect Ratio)", [
        "9:16 (Shorts/Reels/TikTok)",
        "16:9 (YouTube Standard)",
        "1:1 (Square Instagram Post)"
    ])
    length_desc = st.selectbox("Desired Video Length", [
        "Very Short (~15-30 seconds)",
        "Short (~30-60 seconds)",
        "Medium (~1-2 minutes)"
    ])

st.markdown("<br>", unsafe_allow_html=True)

# Use entered API key or session state API key
active_api_key = api_key_input.strip() if api_key_input.strip() else st.session_state.get("api_key", "")

if st.button("Generate Video 🚀", use_container_width=True):
    if not active_api_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar and click 'Apply API Key'.")
    elif not topic.strip():
        st.error("⚠️ Please enter a topic or script for the video.")
    else:
        # Keep session state synced
        st.session_state["api_key"] = active_api_key
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(message, percent):
            status_text.text(f"🔄 {message}")
            progress_bar.progress(percent / 100.0)

        try:
            with st.spinner("Initializing generation process..."):
                final_video_path = generate_video(
                    api_key=active_api_key,
                    topic=topic.strip(),
                    length_desc=length_desc,
                    aspect_ratio=aspect_ratio,
                    output_dir=output_folder,
                    progress_callback=update_progress
                )
            
            st.success(f"✅ Video generated successfully! Saved to: {final_video_path}")
            st.video(final_video_path)
            
        except Exception as e:
            st.error(f"❌ An error occurred during video generation: {str(e)}")
            with st.expander("Show detailed error log"):
                st.code(traceback.format_exc())
