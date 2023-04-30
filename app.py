from datetime import datetime
import os
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
from tqdm import tqdm
import io
import requests
import zipfile
import openai
import uuid
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "_")

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
        zip = zip_audios(sliced_audios)
        print('Request sent')
        return StreamingResponse(io.BytesIO(zip), headers={'Content-Disposition': 'attachment; filename=audio.zip', "Content-Type": "application/zip"})

    else:
        raise HTTPException(status_code=404, detail="Invalid audio file")


@app.get('/download')
def fetch_and_slice_audio(audio_url):
    print('Downloading:', audio_url)
    response = requests.get(audio_url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size=1024 * 1024), total=total_size // 1024 / 1024, unit='MB', unit_scale=True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        audio = AudioSegment.from_file(io.BytesIO(content))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        zip = zip_audios(sliced_audios)
        print('Request sent')
        return StreamingResponse(zip, headers={'Content-Disposition': 'attachment; filename=audio.zip', "Content-Type": "application/zip"})
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")


@app.get('/transcript')
def transcript(audio_url: str, srt: bool):
    print('Downloading:', audio_url)
    print('Srt format', srt)
    response = requests.get(audio_url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size=1024 * 1024), total=total_size // 1024 / 1024, unit='MB', unit_scale=True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        audio = AudioSegment.from_file(io.BytesIO(content))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        results = []
        for audio in sliced_audios:
            slice_io = io.BytesIO()
            audio.export(slice_io, format="mp3")
            slice_io.seek(0)
            with open('./audio.mp3', "wb") as f:
                f.write(slice_io.read())
            with open('./audio.mp3', "rb") as f:
                transcript = openai.Audio.transcribe("whisper-1", f, api_key=OPENAI_API_KEY, response_format=format)
                results.append(transcript if srt else transcript.text)
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")

@app.post('/transcript')
def transcript_file(file: UploadFile, srt: bool = False):
    if file and allowed_file(file.filename):
        audio = AudioSegment.from_file(file.file)
        format = 'srt' if srt else 'text'
        print('audio length:', len(audio))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        results = []
        for audio in sliced_audios:
            slice_io = io.BytesIO()
            audio.export(slice_io, format="mp3")
            slice_io.seek(0)
            filename = '/tmp/' + str(uuid.uuid4()) + '.mp3'
            with open(filename, "wb") as f:
                f.write(slice_io.read())
            with open(filename, "rb") as f:
                transcript = openai.Audio.transcribe("whisper-1", f, api_key=OPENAI_API_KEY, response_format=format)
                print(transcript)
                results.append(transcript if srt else transcript)
            os.remove(filename)
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="No file found")