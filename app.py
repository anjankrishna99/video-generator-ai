import streamlit as st
import os
from video_generator import generate_video
import traceback

st.set_page_config(page_title="AI Video Generator", page_icon="🎥", layout="wide")

# Apply some custom CSS for a premium feel
st.markdown("""
<style>
    .stButton>button {
        background-color: #ff4b4b;
        color: white;
        border-radius: 8px;
        height: 50px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #ff3333;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4);
    }
</style>
""", unsafe_allow_html=True)

st.title("🎥 Local AI Video Generator")
st.markdown("Generate short-form videos for social media powered by **Gemini 1.5 Pro** and Free AI Image endpoints.")

with st.sidebar:
    st.header("Settings ⚙️")
    api_key = st.text_input("Gemini API Key", type="password", help="Get this from Google AI Studio")
    st.markdown("[Get your free Gemini API Key here](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
    # Default to a Downloads folder on the Desktop or User dir
    default_dl = os.path.join(os.path.expanduser("~"), "Downloads")
    output_folder = st.text_input("Download Destination Folder", value=default_dl)

col1, col2 = st.columns([2, 1])

with col1:
    topic = st.text_area("What should the video be about or write your script:", 
                         height=200, 
                         placeholder="e.g. 5 facts about space that will blow your mind... OR \n[Paste your full script here]")
    
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

if st.button("Generate Video 🚀", use_container_width=True):
    if not api_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar.")
    elif not topic:
        st.error("⚠️ Please enter a topic or script for the video.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(message, percent):
            status_text.text(f"🔄 {message}")
            progress_bar.progress(percent / 100.0)

        try:
            with st.spinner("Initializing generation process..."):
                final_video_path = generate_video(
                    api_key=api_key,
                    topic=topic,
                    length_desc=length_desc,
                    aspect_ratio=aspect_ratio,
                    output_dir=output_folder,
                    progress_callback=update_progress
                )
            
            st.success(f"✅ Video generated successfully! Saved to: {final_video_path}")
            
            # Display video
            st.video(final_video_path)
            
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            with st.expander("Show detailed error log"):
                st.code(traceback.format_exc())
