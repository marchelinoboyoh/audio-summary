from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
import speech_recognition as sr
from pydub import AudioSegment
import openai
from docx import Document
import io
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'mp3', 'mp4'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No selected file'})

        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                text = convert_audio_to_text(filepath)

                return jsonify({'original_text': text})

            except Exception as e:
                return jsonify({'error': f"Error processing file: {str(e)}"})

        else:
            return jsonify({'error': 'File type not allowed'})

    return render_template('index.html')

@app.route('/enhance', methods=['POST'])
def enhance_text():
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({'error': 'No text provided'})

    enhanced_text = process_text_with_gpt4(text)
    return jsonify({'enhanced_text': enhanced_text})

@app.route('/download', methods=['POST'])
def download_document():
    try:
        data = request.get_json()
        enhanced_text = data.get('enhanced_text', '')

        if not enhanced_text:
            return jsonify({'error': 'No enhanced text provided'})

        # Create a new Word document
        document = Document()
        document.add_paragraph(enhanced_text)

        # Save the document to a BytesIO buffer
        buffer = io.BytesIO()
        document.save(buffer)
        buffer.seek(0)

        # Send the document as a downloadable file
        return send_file(buffer, as_attachment=True, download_name='enhanced_text.docx', mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        return jsonify({'error': f"Error generating document: {str(e)}"}), 500

def convert_audio_to_text(audio_file):
    recognizer = sr.Recognizer()
    audio_text = ""

    try:
        _, file_extension = os.path.splitext(audio_file)

        if file_extension == '.mp3':
            wav_file = audio_file.replace('.mp3', '.wav')
            audio = AudioSegment.from_mp3(audio_file)
            audio.export(wav_file, format='wav')
            audio_file = wav_file

        # Recognize speech using Google Speech Recognition
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source, duration=60)  # Recognize up to 60 seconds

            # Language detection based on the content
            recognized_lang = recognizer.recognize_google(audio_data, language='zh-CN')  # Recognize in Indonesian
            if 'zh' in recognized_lang.lower():  # Check if Indonesian language detected
                audio_text = recognizer.recognize_google(audio_data, language='zh-CN')  # Recognize in Indonesian
            else:
                audio_text = recognizer.recognize_google(audio_data, language='en-US')  # Recognize in English by default

    except sr.UnknownValueError:
        audio_text = "Could not understand audio"
    except sr.RequestError as e:
        audio_text = f"Error: {e}"
    except Exception as e:
        audio_text = f"Error processing audio: {str(e)}"

    return audio_text

def process_text_with_gpt4(text):
    try:
        openai.api_key = os.getenv('OPENAI_API_KEY')

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "please summarize the text, explain and present it in key points"},
                {"role": "user", "content": text}
            ],
            max_tokens=150
        )

        enhanced_text = response.choices[0].message['content'].strip()

    except Exception as e:
        enhanced_text = f"Error enhancing text: {str(e)}"

    return enhanced_text

if __name__ == '__main__':
    app.run(debug=True)
