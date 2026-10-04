from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
import os
import tempfile
import requests
import base64
from dotenv import load_dotenv

# Load local .env file when running on your computer
load_dotenv()

app = Flask(__name__)

# Allow frontend requests
CORS(app)

# Read API keys from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MURF_AI_API_KEY = os.environ.get("MURF_AI_API_KEY")

# Make sure required API keys exist
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

if not MURF_AI_API_KEY:
    raise RuntimeError("MURF_AI_API_KEY is not set")

# Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


PROMPTS = {
    "Summary": """
You are a professional tourist guide.
Provide a high-level overview of "{place}" in {language}.

Focus on:
- The historical significance
- Why the place is famous
- Key architectural or cultural highlights

Keep the explanation concise, engaging, and easy to follow.
Avoid excessive details and dates.
Limit the response to around 200 words.

Respond ONLY in {language}.
""",

    "Detailed": """
You are a professional tourist guide.
Provide a detailed and immersive explanation of "{place}" in {language}.

Cover:
- Historical background and timeline
- Architectural design and unique features
- Cultural importance and notable events
- Interesting facts and visitor insights

Explain concepts clearly and in a storytelling manner.
Include relevant details and examples to create a rich experience.
Limit the response to around 400 words.

Respond ONLY in {language}.
"""
}


def generate_description(place, answer_type, language):
    prompt = PROMPTS[answer_type].format(
        place=place,
        language=language
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    return response.text


def generate_speech(text, voice_id, locale):

    temp_audio = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False
    )

    url = "https://global.api.murf.ai/v1/speech/stream"

    headers = {
        "api-key": MURF_AI_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "voice_id": voice_id,
        "text": text,
        "locale": locale,
        "model": "falcon-2",
        "format": "MP3",
        "sampleRate": 24000,
        "channelType": "MONO"
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=120
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Murf API error: {response.status_code} - {response.text}"
        )

    with open(temp_audio.name, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    return temp_audio.name


@app.get("/")
def home():
    return jsonify({
        "status": "success",
        "message": "Travel Guide API is running"
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/generate-audio-guide", methods=["POST"])
def generate_audio_guide():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    required_fields = [
        "place",
        "answerType",
        "language",
        "voiceId",
        "locale"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"Missing field: {field}"
            }), 400

    place = data["place"]
    answer_type = data["answerType"]
    language = data["language"]
    voice_id = data["voiceId"]
    locale = data["locale"]

    if answer_type not in PROMPTS:
        return jsonify({
            "error": "Invalid answerType"
        }), 400

    try:

        # Generate description using Gemini
        text_description = generate_description(
            place,
            answer_type,
            language
        )

        # Generate speech using Murf
        audio_path = generate_speech(
            text_description,
            voice_id,
            locale
        )

        # Read audio
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Delete temporary file
        try:
            os.remove(audio_path)
        except OSError:
            pass

        # Convert audio to Base64
        encoded_audio = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        return jsonify({
            "description": text_description,
            "audioBase64": encoded_audio
        })

    except Exception as e:

        print("Error:", str(e))

        return jsonify({
            "error": "Failed to generate audio guide",
            "details": str(e)
        }), 500