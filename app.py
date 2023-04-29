from datetime import datetime
from typing import Annotated
from fastapi import FastAPI, Form, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
from tqdm import tqdm
import io
import requests
import zipfile
from fastapi.middleware.cors import CORSMiddleware

config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300,
    "MAX_CONTENT_LENGTH": 100 * 1024 * 1024  # 100 MB max upload limit
}

ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'}

app = FastAPI()

origins = [
    "https://recos.vercel.app",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def slice_audio(audio, slice_duration):
    startTime = datetime.now()
    slices = []
    duration = len(audio)
    start = 0
    end = slice_duration

    while start <= duration:
        slices.append(audio[start:end])
        start += slice_duration
        end += slice_duration

    endTime = datetime.now()
    print('Slicing took', endTime - startTime)
    return slices


def zip_audios(sliced_audios):
    # Combine the sliced audio files into a single response
    with io.BytesIO() as zip_buffer:
        start_time = datetime.now()
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for idx, audio in enumerate(sliced_audios):
                slice_io = io.BytesIO()
                audio.export(slice_io, format="mp3")
                slice_io.seek(0)
                zipf.writestr(f'slice_{idx+1}.mp3', slice_io.read())
        zip_buffer.seek(0)
        end_time = datetime.now()
        print('Zip took', end_time - start_time)
        return zip_buffer.read()


@app.post('/upload')
def upload_file(file: UploadFile):
    if file and allowed_file(file.filename):
        audio = AudioSegment.from_file(file.file)
        print('audio length:', len(audio))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        def generate():
            for file in sliced_audios:
                slice_io = io.BytesIO()
                file.export(slice_io, format="mp3")
                slice_io.seek(0)
                yield from slice_io
        return StreamingResponse(generate(), headers={'Content-Disposition': 'attachment; filename=audio.tar.gz'})

    else:
        raise HTTPException(status_code=404, detail="Invalid audio file")
    

@app.get('/download')
def fetch_and_slice_audio(audio_url):
    print('Downloading:', audio_url)
    response = requests.get(audio_url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size = 1024 * 1024), total = total_size // 1024 / 1024 , unit = 'MB', unit_scale = True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        audio = AudioSegment.from_file(io.BytesIO(content))
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)  # Slice into max 20-minute chunks
        print('Request sent')
        def generate():
            for file in sliced_audios:
                slice_io = io.BytesIO()
                file.export(slice_io, format="mp3")
                slice_io.seek(0)
                yield from slice_io
        return StreamingResponse(generate(), headers={'Content-Disposition': 'attachment; filename=audio.tar.gz'})
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")


# @app.post('/transcript')
# def transcriptWithModelz():
#     if 'file' not in request.files:
#         flash('No file part')
#         return jsonify({'error': 'No file part'}), 400
#     file = request.files['file']
#     if file and allowed_file(file.filename):
#         srt = transcript(file)
#         return Response(srt, headers={
#             'Content-Disposition': 'attachment; filename=audio.zip',
#             'Content-Type': 'application/zip'
#         })