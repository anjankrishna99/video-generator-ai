import os
import json
import re
import io
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
    """Generate TTS audio using edge-tts with fallbacks."""
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

def create_fallback_image(image_path, prompt, width, height, scene_num=1):
    """Generates a high-quality stylized gradient image if online image generator is unavailable."""
    img = Image.new("RGB", (width, height), color=(20, 24, 33))
    draw = ImageDraw.Draw(img)
    
    # Draw simple gradient effect
    for y in range(height):
        r = int(20 + (y / height) * 30)
        g = int(24 + (y / height) * 40)
        b = int(33 + (y / height) * 60)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # Add decorative frame accent
    border_margin = int(width * 0.05)
    draw.rectangle(
        [border_margin, border_margin, width - border_margin, height - border_margin],
        outline=(255, 75, 75),
        width=4
    )
    
    # Add scene text
    clean_prompt = prompt[:120] + ("..." if len(prompt) > 120 else "")
    display_text = f"Scene {scene_num}\n\n{clean_prompt}"
    
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
        
    # Draw text in center
    draw.text((width // 2, height // 2), display_text, fill=(240, 240, 240), font=font, anchor="mm")
    
    img.save(image_path, "JPEG", quality=90)

def fetch_image(img_prompt, width, height, image_path, scene_num=1):
    """Downloads image from free AI image API with fallback to local graphic generation."""
    safe_prompt = urllib.parse.quote(img_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(image_url, headers=headers, timeout=20)
        if res.status_code == 200 and len(res.content) > 1000:
            test_img = Image.open(io.BytesIO(res.content))
            test_img.verify()
            with open(image_path, "wb") as f:
                f.write(res.content)
            return
    except Exception:
        pass
        
    # Fallback image generation if network/API fails
    create_fallback_image(image_path, img_prompt, width, height, scene_num=scene_num)

def generate_script_json(api_key, topic, length_desc, aspect_ratio):
    """Generates structured script JSON using Gemini API with multi-model fallback."""
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
    last_error = None
    candidate_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-pro']

    # 1. Try modern google.genai SDK
    try:
        from google import genai as new_genai
        client = new_genai.Client(api_key=api_key)
        for model_name in candidate_models:
            try:
                resp = client.models.generate_content(model=model_name, contents=prompt)
                if resp and resp.text:
                    raw_text = resp.text.strip()
                    break
            except Exception as e:
                last_error = e
                continue
    except Exception as e:
        last_error = e

    # 2. Try legacy google.generativeai SDK
    if not raw_text:
        try:
            genai.configure(api_key=api_key)
            for model_name in candidate_models:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    if resp and resp.text:
                        raw_text = resp.text.strip()
                        break
                except Exception as e:
                    last_error = e
                    continue
        except Exception as e:
            last_error = e

    if not raw_text:
        raise RuntimeError(f"Could not generate script with Gemini API. Error details: {last_error}")

    # Extract JSON block using regex if present
    json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
    else:
        json_str = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        script = json.loads(json_str)
        if isinstance(script, list) and len(script) > 0:
            return script
    except Exception:
        pass

    # Safe structured fallback if JSON parsing fails
    return [
        {
            "voiceover": f"Welcome! Today we are exploring {topic}.",
            "image_prompt": f"A vibrant title background for {topic}"
        },
        {
            "voiceover": f"Here is what makes {topic} so interesting and unique.",
            "image_prompt": f"Detailed cinematic illustration about {topic}"
        },
        {
            "voiceover": "Thanks for watching! Like and subscribe for more amazing content.",
            "image_prompt": "Outro social media background with subscribe icons"
        }
    ]

def generate_video(api_key, topic, length_desc, aspect_ratio, output_dir, progress_callback=None):
    """Main video generation pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_assets")
    os.makedirs(temp_dir, exist_ok=True)

    if progress_callback:
        progress_callback("Generating script with Gemini AI...", 10)
    
    # 1. Generate Script
    script = generate_script_json(api_key, topic, length_desc, aspect_ratio)

    # 2. Setup Dimensions based on aspect ratio
    width, height = (1080, 1920) if "9:16" in aspect_ratio else (1920, 1080)
    if "1:1" in aspect_ratio:
        width, height = (1080, 1080)

    clips = []
    audio_clips_to_close = []
    total_scenes = len(script)

    try:
        for i, scene in enumerate(script):
            scene_num = i + 1
            if progress_callback:
                progress_callback(f"Processing scene {scene_num}/{total_scenes}...", 20 + int((i / total_scenes) * 60))
            
            voiceover = scene.get("voiceover", f"Scene {scene_num} about {topic}")
            img_prompt = scene.get("image_prompt", f"Visual for {topic}")
            
            # Generate Audio using thread-isolated async loop
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            audio_success = run_async_in_thread(generate_audio_async(voiceover, audio_path))
            
            if audio_success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                audio_clip = AudioFileClip(audio_path)
            else:
                duration = 4.0
                audio_clip = AudioClip(lambda t: 0, duration=duration)
                
            audio_clips_to_close.append(audio_clip)

            # Generate Image
            image_path = os.path.join(temp_dir, f"image_{i}.jpg")
            fetch_image(img_prompt, width, height, image_path, scene_num=scene_num)

            # Create Image Clip matching audio duration
            clip_duration = max(audio_clip.duration if hasattr(audio_clip, 'duration') and audio_clip.duration else 4.0, 2.0)
            img_clip = ImageClip(image_path).set_duration(clip_duration)
            img_clip = img_clip.set_audio(audio_clip)
            
            clips.append(img_clip)

        if not clips:
            raise RuntimeError("No video clips were created.")

        if progress_callback:
            progress_callback("Stitching final video clips...", 85)

        # 3. Concatenate and Render
        final_video = concatenate_videoclips(clips, method="compose")
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic])[:15]
        output_file = os.path.join(output_dir, f"generated_video_{safe_topic}.mp4")
        
        if progress_callback:
            progress_callback("Rendering MP4 video file...", 92)

        final_video.write_videofile(
            output_file, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None,
            threads=2
        )
            
        if progress_callback:
            progress_callback("Video generation complete!", 100)
            
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
