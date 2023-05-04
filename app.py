import os
import io
import requests
import zipfile
import openai
import uuid
import json
from jose import jwe
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from datetime import datetime
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydub import AudioSegment
from tqdm import tqdm
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from credit import get_user_credit, update_user_credit

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "_")
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'}

app = FastAPI()

origins = [
    "https://recos.vercel.app",
    "http://localhost:3000",
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"",
        info="NextAuth.js Generated Encryption Key".encode(),
    )
    key = hkdf.derive(os.environ.get('JWT_SECRET').encode())
    user = jwe.decrypt(token, key).decode()
    return json.loads(user)

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
def transcript(url: str, current_user: Annotated[User, Depends(get_current_user)], srt: bool = False ):
    print('Downloading:', url)
    print('Srt format', srt)
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size=1024 * 1024), total=total_size // 1024 / 1024, unit='MB', unit_scale=True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        credit = get_user_credit(current_user['sub'])
        audio = AudioSegment.from_file(io.BytesIO(content))
        duration = round(audio.duration_seconds / 60)
        if(duration > credit):
            raise HTTPException(status_code=404, detail="Insufficient credit")
        format = 'srt' if srt else 'text'
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
                results.append(transcript if srt else transcript.text)
            os.remove(filename)
        update_user_credit(current_user['sub'], -duration)
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")

@app.post('/transcript')
def transcript_file(file: UploadFile,  current_user: Annotated[User, Depends(get_current_user)], srt: bool = False,):
    if file and allowed_file(file.filename):
        credit = get_user_credit(current_user['sub'])
        audio = AudioSegment.from_file(file.file)
        duration = round(audio.length_seconds / 60)
        if(duration > credit):
            raise HTTPException(status_code=404, detail="Insufficient credit")
        format = 'srt' if srt else 'text'
        print('Audio length:', len(audio))
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
        update_user_credit(current_user['sub'], -duration)
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="No file found")
