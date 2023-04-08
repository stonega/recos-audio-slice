from flask import Flask, send_file, request, jsonify
from pydub import AudioSegment
import io
import requests

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload limit

@app.route('/')
def hello_world():
    return 'Hello, World!'

def slice_audio(audio, slice_duration):
    slices = []
    duration = len(audio)
    start = 0
    end = slice_duration

    while start <= duration:
        slices.append(audio[start:end])
        start += slice_duration
        end += slice_duration

    return slices


@app.route('/upload', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        audio = AudioSegment.from_file(file)
        sliced_audios = slice_audio(audio, 10 * 60 * 1000)  # Slice into max 10-minute chunks
        
        # Combine the sliced audio files into a single response
        result_bytes = io.BytesIO()
        for idx, audio in enumerate(sliced_audios):
            slice_io = io.BytesIO()
            audio.export(slice_io, format="mp3")
            slice_io.seek(0)

            if idx == 0:
                result_bytes.write(b'--sliceseparator\r\n')
            result_bytes.write(slice_io.read())
            result_bytes.write(b'\r\n--sliceseparator\r\n')

        result_bytes.seek(0)

        return send_file(result_bytes, mimetype='audio/mpeg', as_attachment=True, attachment_filename='sliced_audio.mp3')
    
@app.route('/fetch', methods=['GET'])
def fetch_and_slice_audio():
    if request.method == 'GET':
        audio_url = request.query['url']

        response = requests.get(audio_url)
        if response.status_code == 200:
            audio = AudioSegment.from_file(io.BytesIO(response.content))
            sliced_audios = slice_audio(audio, 10 * 60 * 1000)  # Slice into max 10-minute chunks

            # Combine the sliced audio files into a single response
            result_bytes = io.BytesIO()
            for idx, audio in enumerate(sliced_audios):
                slice_io = io.BytesIO()
                audio.export(slice_io, format="mp3")
                slice_io.seek(0)

                if idx == 0:
                    result_bytes.write(b'--sliceseparator\r\n')
                result_bytes.write(slice_io.read())
                result_bytes.write(b'\r\n--sliceseparator\r\n')

            result_bytes.seek(0)

            return send_file(result_bytes, mimetype='audio/mpeg', as_attachment=True, attachment_filename='sliced_audio.mp3')
        else:
            return jsonify({'error': 'Failed to fetch the audio URL'}), 404