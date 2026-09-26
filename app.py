import streamlit as st
import os
import traceback
from dotenv import load_dotenv, set_key
import video_generator
import importlib
importlib.reload(video_generator)
from video_generator import generate_video, generate_standalone_image

# Load environment variables from .env file if present
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_FILE)

st.set_page_config(page_title="AI Studio - Video & Image Generator", page_icon="🎬", layout="wide")

st.markdown("<style>.stButton>button { background-color: #ff4b4b; color: white; border-radius: 8px; height: 48px; font-weight: bold; transition: all 0.3s ease; } .stButton>button:hover { background-color: #ff3333; box-shadow: 0 4px 12px rgba(255, 75, 75, 0.4); }</style>", unsafe_allow_html=True)

st.title("🎬 AI Studio: Video & Image Generator")
st.markdown("Create viral AI videos and photorealistic artwork powered by **Gemini AI** and **FLUX**.")

# Initialize session state for API key
if "api_key" not in st.session_state:
    st.session_state["api_key"] = os.getenv("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("Settings ⚙️")
    
    api_key_input = st.text_input(
        "Gemini API Key (Required for Videos)", 
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
            except Exception:
                st.sidebar.info("✅ API Key applied for session!")
                
    st.divider()
    
    default_dl = os.path.join(os.path.dirname(__file__), "outputs")
    output_folder = st.text_input("Download Destination Folder", value=default_dl)

active_api_key = api_key_input.strip() if api_key_input.strip() else st.session_state.get("api_key", "")

# Main App Navigation with Tabs
tab_video, tab_image = st.tabs(["🎥 Video Generator", "🖼️ Image Generator"])

with tab_video:
    st.subheader("🎥 AI Video Generator")
    st.caption("Generate complete short-form videos with Flux AI visuals, voiceover narration, and dynamic subtitles.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_area(
            "What should the video be about or write your script:", 
            height=200, 
            placeholder="e.g. 5 fascinating facts about space that will blow your mind... OR paste your full script here.",
            key="video_topic"
        )
        
    with col2:
        aspect_ratio = st.selectbox("Video Format (Aspect Ratio)", [
            "9:16 (Shorts/Reels/TikTok)",
            "16:9 (YouTube Standard)",
            "1:1 (Square Instagram Post)"
        ], key="video_aspect")
        
        length_desc = st.selectbox("Desired Video Length", [
            "Very Short (~15-30 seconds)",
            "Short (~30-60 seconds)",
            "Medium (~1-2 minutes)"
        ], key="video_length")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Generate Video 🚀", use_container_width=True, key="btn_gen_video"):
        if not topic.strip():
            st.error("⚠️ Please enter a topic or script for the video.")
        else:
            st.session_state["api_key"] = active_api_key
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, percent):
                status_text.text(f"🔄 {message}")
                progress_bar.progress(percent / 100.0)

            try:
                with st.spinner("Creating your cinematic AI video..."):
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
                
                # Provide instant download button for the video
                with open(final_video_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Video (MP4)",
                        data=f,
                        file_name=os.path.basename(final_video_path),
                        mime="video/mp4"
                    )
                
            except Exception as e:
                st.error(f"❌ An error occurred during video generation: {str(e)}")
                with st.expander("Show detailed error log"):
                    st.code(traceback.format_exc())

with tab_image:
    st.subheader("🖼️ AI Image Generator")
    st.caption("Generate state-of-the-art AI images powered by FLUX with custom aesthetics.")
    
    col_img_1, col_img_2 = st.columns([2, 1])
    
    with col_img_1:
        img_prompt = st.text_area(
            "Describe the image you want to create in detail:",
            height=180,
            placeholder="e.g. A futuristic cyberpunk supercar parked on a wet neon street in Tokyo at midnight, reflections, 8k resolution, cinematic lighting",
            key="image_prompt"
        )
        
    with col_img_2:
        img_aspect = st.selectbox("Image Aspect Ratio", [
            "1:1 (Square - Instagram/Avatar)",
            "16:9 (Landscape - Wallpaper/Desktop)",
            "9:16 (Portrait - Stories/Phone)",
            "4:3 (Classic Landscape)",
            "3:4 (Classic Portrait)"
        ], key="img_aspect")
        
        img_style = st.selectbox("Art Style", [
            "Photorealistic",
            "Cinematic Movie Shot",
            "Anime / Studio Ghibli",
            "3D Digital Art",
            "Cyberpunk Neon",
            "Fantasy Concept Art",
            "Oil Painting"
        ], key="img_style")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("Generate Image 🎨", use_container_width=True, key="btn_gen_img"):
        if not img_prompt.strip():
            st.error("⚠️ Please describe the image you want to generate.")
        else:
            try:
                with st.spinner("Generating photorealistic artwork with FLUX..."):
                    generated_img_path = generate_standalone_image(
                        prompt=img_prompt.strip(),
                        aspect_ratio=img_aspect,
                        style=img_style,
                        output_dir=output_folder
                    )
                    
                st.success("✅ Image generated successfully!")
                st.image(generated_img_path, use_container_width=True)
                
                # Provide instant download button for the image
                with open(generated_img_path, "rb") as f:
                    st.download_button(
                        label="📥 Download High-Res Image (JPG)",
                        data=f,
                        file_name=os.path.basename(generated_img_path),
                        mime="image/jpeg"
                    )
            except Exception as e:
                st.error(f"❌ Failed to generate image: {str(e)}")
                with st.expander("Show detailed error log"):
                    st.code(traceback.format_exc())
