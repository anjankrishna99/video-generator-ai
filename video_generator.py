import os
import json
import urllib.parse
import requests
import asyncio
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

async def generate_audio(text, output_filename):
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_filename)

def generate_video(api_key, topic, length_desc, aspect_ratio, output_dir, progress_callback=None):
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_assets")
    os.makedirs(temp_dir, exist_ok=True)

    if progress_callback:
        progress_callback("Generating script with Gemini...", 10)
    
    # 1. Generate Script
    prompt = f"""
    Write a short engaging script for a {length_desc} video about: {topic}.
    The video aspect ratio is {aspect_ratio}.
    Output strictly in JSON format as a list of scenes.
    Do not use markdown formatting like ```json. Just return the raw JSON array.
    Each object in the array must have:
    - "voiceover": the text to be spoken in the scene.
    - "image_prompt": a detailed description of the visual scene for an AI image generator. Ensure it fits a {aspect_ratio} orientation.
    """

    raw_text = None
    last_error = None
    candidate_models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']

    # Try modern google.genai SDK first
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

    # Fallback to google.generativeai SDK if modern SDK didn't return text
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

    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    try:
        script = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response as JSON: {raw_text}") from e

    # 2. Process Scenes
    clips = []
    total_scenes = len(script)
    
    width, height = (1080, 1920) if "9:16" in aspect_ratio else (1920, 1080)
    if "1:1" in aspect_ratio:
        width, height = (1080, 1080)

    for i, scene in enumerate(script):
        if progress_callback:
            progress_callback(f"Processing scene {i+1}/{total_scenes}...", 20 + int((i/total_scenes)*60))
        
        voiceover = scene.get("voiceover", "")
        img_prompt = scene.get("image_prompt", "")
        
        # Generate Audio
        audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
        # Run async function in sync context safely
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_audio(voiceover, audio_path))
        
        audio_clip = AudioFileClip(audio_path)
        
        # Generate Image (using Pollinations.ai free endpoint)
        safe_prompt = urllib.parse.quote(img_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true"
        image_path = os.path.join(temp_dir, f"image_{i}.jpg")
        
        img_data = requests.get(image_url).content
        with open(image_path, "wb") as handler:
            handler.write(img_data)
            
        # Create Image Clip matching audio duration
        img_clip = ImageClip(image_path).set_duration(audio_clip.duration)
        img_clip = img_clip.set_audio(audio_clip)
        
        clips.append(img_clip)

    if progress_callback:
        progress_callback("Stitching final video...", 90)

    # 3. Concatenate and Render
    final_video = concatenate_videoclips(clips, method="compose")
    safe_topic = "".join([c if c.isalnum() else "_" for c in topic])[:15]
    output_file = os.path.join(output_dir, f"generated_video_{safe_topic}.mp4")
    
    # Write videofile
    final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac", logger=None)
                                
    # Clean up clips to free memory
    for c in clips:
        c.close()
    final_video.close()
        
    if progress_callback:
        progress_callback("Video generation complete!", 100)
        
    return output_file
