import os
import json
import re
import io
import time
import urllib.parse
import requests
import asyncio
import threading
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, AudioClip

def run_async_in_thread(coro):
    """Executes a coroutine safely in an isolated thread with its own event loop."""
    res_container = []
    err_container = []

    def target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(coro)
            res_container.append(res)
            loop.close()
        except Exception as e:
            err_container.append(e)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=35)
    
    if err_container:
        return None
    return res_container[0] if res_container else None

async def generate_audio_async(text, output_filename):
    """Generate TTS audio using edge-tts with voice fallbacks."""
    voices = ["en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-AriaNeural"]
    for voice in voices:
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_filename)
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                return True
        except Exception:
            continue
    return False

def create_artistic_backdrop(image_path, width, height, scene_num=1):
    """Generates an aesthetic ambient gradient backdrop (never writes raw prompt text)."""
    img = Image.new("RGB", (width, height), color=(15, 20, 30))
    draw = ImageDraw.Draw(img)
    
    # Modern dark tech / cinematic gradient
    for y in range(height):
        ratio = y / height
        r = int(12 + ratio * 28 + (scene_num * 5) % 30)
        g = int(18 + ratio * 35 + (scene_num * 8) % 30)
        b = int(32 + ratio * 65 + (scene_num * 12) % 40)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # Add ambient glow ring in the center
    cx, cy = width // 2, height // 2
    glow_r = int(min(width, height) * 0.35)
    draw.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r], outline=(255, 75, 75), width=3)
    
    img.save(image_path, "JPEG", quality=90)

def overlay_subtitles(image_path, voiceover_text, width, height):
    """Overlays social-media style subtitles onto the image."""
    try:
        img = Image.open(image_path).convert("RGBA")
        
        # Word wrap text for readability
        words = voiceover_text.split()
        lines = []
        cur_line = []
        for w in words:
            cur_line.append(w)
            if len(" ".join(cur_line)) > 26:
                lines.append(" ".join(cur_line))
                cur_line = []
        if cur_line:
            lines.append(" ".join(cur_line))
            
        subtitle_text = "\n".join(lines[:3])
        
        try:
            font_size = max(int(height * 0.032), 22)
            font = ImageFont.truetype("arial.ttf", size=font_size)
        except Exception:
            font = ImageFont.load_default()
            
        draw = ImageDraw.Draw(img)
        margin_y = int(height * 0.82)
        
        # Measure text box
        bbox = draw.multiline_textbbox((width // 2, margin_y), subtitle_text, font=font, anchor="mm", align="center")
        pad = 18
        bg_box = [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad]
        
        # Translucent dark pill overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(bg_box, radius=14, fill=(0, 0, 0, 200))
        
        combined = Image.alpha_composite(img, overlay).convert("RGB")
        
        # Render crisp white text
        final_draw = ImageDraw.Draw(combined)
        final_draw.multiline_text((width // 2, margin_y), subtitle_text, fill=(255, 255, 255), font=font, anchor="mm", align="center")
        
        combined.save(image_path, "JPEG", quality=92)
    except Exception:
        pass

def fetch_image(img_prompt, width, height, image_path, scene_num=1):
    """Downloads real AI generated visuals based on visual keywords."""
    # 1. Distill prompt to clean visual subject keywords (prevents API timeouts)
    clean_words = re.sub(r'[^a-zA-Z0-9\s]', ' ', img_prompt).split()
    fillers = {"a", "an", "the", "in", "of", "and", "or", "for", "with", "detailed", 
               "orientation", "aspect", "ratio", "image", "prompt", "visual", "fits", 
               "scene", "depicting", "illustration", "photorealistic", "cinematic", "showing"}
    filtered = [w for w in clean_words if w.lower() not in fillers]
    concise_prompt = " ".join(filtered[:10]) if filtered else "dynamic cinematic landscape"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    safe_prompt = urllib.parse.quote(f"cinematic photorealistic {concise_prompt}")
    seed = int(time.time() * 1000) % 99999 + scene_num * 100
    
    # 2. Try Pollinations AI (free AI image generator)
    pollinations_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true&seed={seed}"
    try:
        res = requests.get(pollinations_url, headers=headers, timeout=25)
        if res.status_code == 200 and len(res.content) > 3000:
            img = Image.open(io.BytesIO(res.content)).convert("RGB")
            img.save(image_path, "JPEG", quality=92)
            return
    except Exception:
        pass

    # 3. Try high-definition photography fallback (real photos, never text)
    try:
        picsum_url = f"https://picsum.photos/{width}/{height}?random={seed}"
        res = requests.get(picsum_url, headers=headers, timeout=12)
        if res.status_code == 200 and len(res.content) > 3000:
            img = Image.open(io.BytesIO(res.content)).convert("RGB")
            img.save(image_path, "JPEG", quality=92)
            return
    except Exception:
        pass

    # 4. Artistic graphic backdrop if offline
    create_artistic_backdrop(image_path, width, height, scene_num=scene_num)

def query_gemini_rest(api_key, prompt):
    """Direct REST fallback to Google Gemini endpoints."""
    endpoints = [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    ]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    for url in endpoints:
        try:
            r = requests.post(f"{url}?key={api_key}", json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except Exception:
            continue
    return None

def generate_smart_topic_script(topic, aspect_ratio):
    """Synthesizes structured scene script directly from the user's input."""
    # Check if the user pasted their own custom script lines
    lines = [line.strip() for line in re.split(r'[\r\n]+', topic) if len(line.strip()) > 5]
    if len(lines) >= 2:
        scenes = []
        for i, line in enumerate(lines[:6]):
            clean_line = re.sub(r'^[0-9]+[\.\-\)]\s*', '', line)
            scenes.append({
                "voiceover": clean_line,
                "image_prompt": f"Dramatic visual depicting {clean_line[:50]}, cinematic lighting, {aspect_ratio}"
            })
        return scenes

    sentences = [s.strip() for s in re.split(r'[.!?]+', topic) if len(s.strip()) > 8]
    if len(sentences) >= 3:
        scenes = []
        for s in sentences[:5]:
            scenes.append({
                "voiceover": s + ".",
                "image_prompt": f"Detailed photorealistic view of {s[:50]}, {aspect_ratio}"
            })
        return scenes

    return [
        {
            "voiceover": f"Welcome! Here is what you need to know about {topic}.",
            "image_prompt": f"Vibrant opening visual introducing {topic}, cinematic 4k, {aspect_ratio}"
        },
        {
            "voiceover": f"The key elements of {topic} reveal surprising facts and unique perspectives.",
            "image_prompt": f"Detailed and engaging visual about {topic}, ultra-sharp details, {aspect_ratio}"
        },
        {
            "voiceover": f"Exploring {topic} shows just how powerful and fascinating this subject is.",
            "image_prompt": f"Dynamic atmospheric shot capturing the essence of {topic}, {aspect_ratio}"
        },
        {
            "voiceover": "Thanks for watching! Like and follow for more exciting updates.",
            "image_prompt": f"Cinematic outro frame for {topic} with elegant lighting, {aspect_ratio}"
        }
    ]

def generate_script_json(api_key, topic, length_desc, aspect_ratio, progress_callback=None):
    """Generates structured script JSON using Gemini with multiple API strategies and fail-proof fallback."""
    clean_key = str(api_key).strip().strip("'").strip('"')
    
    prompt = f"""
    Write a short engaging script for a {length_desc} video about: {topic}.
    The video aspect ratio is {aspect_ratio}.
    Output strictly in JSON format as a list of scenes.
    Do not use markdown formatting or any introductory text. Return only the raw JSON array.
    Each object in the array must have:
    - "voiceover": the text to be spoken in the scene.
    - "image_prompt": a detailed description of the visual scene for an AI image generator. Ensure it fits a {aspect_ratio} orientation.
    """

    raw_text = None

    # Strategy 1: Direct Google Generative Language REST API
    if clean_key:
        if progress_callback:
            progress_callback("Connecting to Gemini API...", 15)
        raw_text = query_gemini_rest(clean_key, prompt)

    # Strategy 2: Google GenAI Modern SDK
    if not raw_text and clean_key:
        try:
            from google import genai as new_genai
            client = new_genai.Client(api_key=clean_key)
            for m in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']:
                try:
                    resp = client.models.generate_content(model=m, contents=prompt)
                    if resp and resp.text:
                        raw_text = resp.text.strip()
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Strategy 3: Dynamic Model Discovery via Legacy SDK
    if not raw_text and clean_key:
        try:
            genai.configure(api_key=clean_key)
            discovered_models = []
            try:
                for m in genai.list_models():
                    if "generateContent" in getattr(m, "supported_generation_methods", []):
                        discovered_models.append(m.name)
            except Exception:
                discovered_models = ['gemini-1.5-flash', 'gemini-pro']

            for model_name in discovered_models:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    if resp and resp.text:
                        raw_text = resp.text.strip()
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Strategy 4: If LLM returned text, parse JSON
    if raw_text:
        json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else raw_text.replace("```json", "").replace("```", "").strip()
        try:
            script = json.loads(json_str)
            if isinstance(script, list) and len(script) > 0:
                return script
        except Exception:
            pass

    # Strategy 5: Smart fail-proof scene synthesis from topic
    if progress_callback:
        progress_callback("Formatting video scene script...", 20)
    return generate_smart_topic_script(topic, aspect_ratio)

def generate_video(api_key, topic, length_desc, aspect_ratio, output_dir, progress_callback=None):
    """Main video generation pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_assets")
    os.makedirs(temp_dir, exist_ok=True)

    if progress_callback:
        progress_callback("Preparing script...", 10)
    
    # 1. Generate Script
    script = generate_script_json(api_key, topic, length_desc, aspect_ratio, progress_callback=progress_callback)

    # 2. Optimized HD resolutions for fast generation and crisp output
    width, height = (720, 1280) if "9:16" in aspect_ratio else (1280, 720)
    if "1:1" in aspect_ratio:
        width, height = (720, 720)

    clips = []
    audio_clips_to_close = []
    total_scenes = len(script)

    try:
        for i, scene in enumerate(script):
            scene_num = i + 1
            if progress_callback:
                progress_callback(f"Generating scene {scene_num}/{total_scenes} audio & visuals...", 20 + int((i / total_scenes) * 60))
            
            voiceover = scene.get("voiceover", f"Scene {scene_num} about {topic}")
            img_prompt = scene.get("image_prompt", f"Visual for {topic}")
            
            # Generate Audio
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            audio_success = run_async_in_thread(generate_audio_async(voiceover, audio_path))
            
            if audio_success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                audio_clip = AudioFileClip(audio_path)
            else:
                duration = 4.0
                audio_clip = AudioClip(lambda t: 0, duration=duration)
                
            audio_clips_to_close.append(audio_clip)

            # Generate Real AI Image based on prompt keywords
            image_path = os.path.join(temp_dir, f"image_{i}.jpg")
            fetch_image(img_prompt, width, height, image_path, scene_num=scene_num)
            
            # Overlay social media subtitles onto the scene
            overlay_subtitles(image_path, voiceover, width, height)

            # Create Image Clip matching audio duration
            clip_duration = max(audio_clip.duration if hasattr(audio_clip, 'duration') and audio_clip.duration else 4.0, 2.0)
            img_clip = ImageClip(image_path).set_duration(clip_duration)
            img_clip = img_clip.set_audio(audio_clip)
            
            clips.append(img_clip)

        if not clips:
            raise RuntimeError("No video clips were created.")

        if progress_callback:
            progress_callback("Stitching and compiling video clips...", 85)

        # 3. Concatenate and Render
        final_video = concatenate_videoclips(clips, method="compose")
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic])[:15]
        output_file = os.path.join(output_dir, f"generated_video_{safe_topic}.mp4")
        
        if progress_callback:
            progress_callback("Rendering final MP4 file...", 92)

        final_video.write_videofile(
            output_file, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None,
            threads=2
        )
            
        if progress_callback:
            progress_callback("Video generation complete! 🎉", 100)
            
        return output_file

    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
        for a in audio_clips_to_close:
            try:
                a.close()
            except Exception:
                pass
