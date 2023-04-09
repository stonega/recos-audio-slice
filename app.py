from flask import Flask, Response, request, jsonify
from pydub import AudioSegment
from tqdm import tqdm
import io
import requests
import zipfile
from flask_caching import Cache
from flask_cors import CORS

config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300,
    "MAX_CONTENT_LENGTH": 100 * 1024 * 1024  # 100 MB max upload limit
}
app = Flask(__name__)
app.config.from_mapping(config)
CORS(app)
cache = Cache(app)

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

def zip_audios(sliced_audios):
    # Combine the sliced audio files into a single response
    with io.BytesIO() as zip_buffer:
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for idx, audio in enumerate(sliced_audios):
                slice_io = io.BytesIO()
                audio.export(slice_io, format="mp3")
                slice_io.seek(0)
                zipf.writestr(f'slice_{idx+1}.mp3', slice_io.read())
        zip_buffer.seek(0)
        return zip_buffer.read()


@app.route('/upload', methods=['POST'])
@cache.cached(timeout=50)
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        audio = AudioSegment.from_file(file)
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)  # Slice into max 10-minute chunks
        zip = zip_audios(sliced_audios)
        return Response(zip, headers={
            'Content-Disposition': 'attachment; filename=audio.zip',
            'Content-Type': 'application/zip'
        })
        
    
@app.route('/download', methods=['GET'])
@cache.cached(timeout=50)
def fetch_and_slice_audio():
    if request.method == 'GET':
        audio_url = request.args['url']
        print('Downloading:', audio_url)
        response = requests.get(audio_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        # Initialize the bytearray
        content = bytearray()

        for data in tqdm(response.iter_content(chunk_size = 1024 * 1024), total = total_size // 1024 / 1024 , unit = 'MB', unit_scale = True):
            content.extend(data)

        if response.status_code == 200:
            audio = AudioSegment.from_file(io.BytesIO(content))
            sliced_audios = slice_audio(audio, 20 * 60 * 1000)  # Slice into max 20-minute chunks
            zip = zip_audios(sliced_audios)
            return Response(zip, headers={
                'Content-Disposition': 'attachment; filename=audio.zip',
                'Content-Type': 'application/zip'
            })
        else:
            return jsonify({'error': 'Failed to fetch the audio URL'}), 404