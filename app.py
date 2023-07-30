import os
import io
import zipfile
import openai
import uuid
import json
import requests
import logging
import multiprocessing
from jose import jwe
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from datetime import datetime
from typing import Annotated
from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from pydub import AudioSegment
from tqdm import tqdm
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from credit import add_credit_record, get_user_credit, update_user_credit
from pytube import YouTube
from fastapi.staticfiles import StaticFiles

from worker import transcript_file_task_add, transcript_task_add
from worker import celery
from celery.signals import task_postrun

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "_")
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'}
ONE_MINUTE = 1000*60
app = FastAPI()

app.mount("/files", StaticFiles(directory="/tmp"), name="files")

origins = [
    "https://recos.vercel.app",
    "https://www.recos.studio",
    "http://localhost:3000",
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    sub: str
    email: str | None = None
    name: str | None = None
    disabled: bool | None = None


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"",
        info="NextAuth.js Generated Encryption Key".encode(),
    )
    secret = os.environ.get('JWT_SECRET')
    if secret is None:
        return None
    else :
        key = hkdf.derive(secret.encode())
        user_decoded = jwe.decrypt(token, key)
        if user_decoded is None:
            return None
        else:
            user = user_decoded.decode()
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

def export_mp3(audio):
    start_time = datetime.now()
    filename = '/tmp/' + str(uuid.uuid4()) + '.mp3'
    audio.export(filename, format="mp3")
    end_time = datetime.now()
    print('Audio saved', filename,  end_time - start_time, sep="---")
    return filename

def save_file(file):
    id = str(uuid.uuid4()) + '_' + file.filename
    filename = '/tmp/' + id
    with open(filename, "wb+") as file_object:
        file_object.write(file.file.read())
    print('Audio saved', filename)
    return id

def transcribe_audio(filename, format, prompt):
    print('Request openapi', filename, format, prompt, sep="---")
    with open(filename, "rb") as f:
        transcript = openai.Audio.transcribe(
            "whisper-1", f, api_key=OPENAI_API_KEY, response_format=format, prompt=prompt)
        os.remove(filename)
        return transcript

def get_youtube_audio_url (link):
    print('Transcribing youtube', link)
    yt = YouTube(link)
    audio = yt.streams.filter(only_audio=True).first()
    if audio is None:
        return 'Failed to fetch url'
    else:
        return audio.url

@app.post('/upload')
def upload_file(file: UploadFile):
    if file and allowed_file(file.filename):
        audio = AudioSegment.from_file(file.file)
        print('audio length:', len(audio))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        zip = zip_audios(sliced_audios)
        logging.info('Request sent')
        return StreamingResponse(io.BytesIO(zip), headers={'Content-Disposition': 'attachment; filename=audio.zip', "Content-Type": "application/zip"})

    else:
        raise HTTPException(status_code=404, detail="Invalid audio file")


@app.get('/download')
async def fetch_and_slice_audio(url):
    print('Downloading:', url)
    # Initialize the bytearray
    response = requests.get(url, stream=True)
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
        return StreamingResponse(io.BytesIO(zip), headers={'Content-Disposition': 'attachment; filename=audio.zip', "Content-Type": "application/zip"})
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")


@app.get('/transcript')
def transcript(url: str, current_user: Annotated[User, Depends(get_current_user)], title: str = '', srt: bool = False, prompt: str = '', type: str = 'audio'):
    if (type == 'youtube'):
        print('Youtube url', url)
        url = get_youtube_audio_url(url)
        print('Youtube audio url', url)
    print('Downloading:', url)
    print('Srt format', srt)
    try:
        response = requests.get(url, stream=True)
    except requests.exceptions.HTTPError as err:
        raise HTTPException(status_code=404, detail="Failed to fetch url")

    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size=1024 * 1024), total=total_size // 1024 / 1024, unit='MB', unit_scale=True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        credit = get_user_credit(current_user['sub'])
        audio = AudioSegment.from_file(io.BytesIO(content))
        duration = round(len(audio) / ONE_MINUTE)
        if (duration > credit):
            raise HTTPException(status_code=404, detail="Insufficient credit")
        format = 'srt' if srt else 'text'
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        # Save files in /tmp
        files = []
        for audio in sliced_audios:
            print('Audio length:', len(audio))
            files.append(export_mp3(audio))
        # Transcribe
        results = []
        inputs = list(map(lambda file:(file, format, prompt), files))
        with multiprocessing.Pool(processes=len(inputs)) as pool:
            results = pool.starmap(transcribe_audio, inputs)
        # Update user credit
        update_user_credit(current_user['sub'], -duration, len(audio), title, 'podcast')
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="Failed to fetch url")


@app.post('/transcript')
def transcript_file(file: UploadFile,  current_user: Annotated[User, Depends(get_current_user)], prompt:  Annotated[str, Form()] = '', srt: Annotated[bool, Form()] = False):
    if file and allowed_file(file.filename):
        credit = get_user_credit(current_user['sub'])
        audio = AudioSegment.from_file(file.file)
        duration = round(len(audio) / ONE_MINUTE)
        if (duration > credit):
            raise HTTPException(status_code=404, detail="Insufficient credit")
        format = 'srt' if srt else 'text'
        print('Audio length:', len(audio))
        # Slice into max 20-minute chunks
        sliced_audios = slice_audio(audio, 20 * 60 * 1000)
        # Export audio files
        files = []
        for audio in sliced_audios:
            print('Audio length:', len(audio))
            files.append(export_mp3(audio))
        results = []
        # Transcribe
        inputs = list(map(lambda file:(file, format, prompt), files))
        with multiprocessing.Pool(processes=len(inputs)) as pool:
            results = pool.starmap(transcribe_audio, inputs)
        # Update user credit
        update_user_credit(current_user['sub'], -duration, len(audio), file.filename, 'audio')
        print('Request sent')
        return results
    else:
        raise HTTPException(status_code=404, detail="No file found")


@app.get("/transcript-task")
def transcript_task(url: str, current_user: Annotated[User, Depends(get_current_user)], title: str = '', srt: bool = False, prompt: str = '', type: str = 'audio'):
    task = transcript_task_add.delay(url, current_user, title, srt, prompt, type)
    add_credit_record(task.id, current_user['sub'], title, 'audio')
    return JSONResponse({"task_id": task.id})

@app.post("/transcript-task")
def transcript_file_task(file: UploadFile, current_user: Annotated[User, Depends(get_current_user)], prompt:  Annotated[str, Form()] = '', srt: Annotated[bool, Form()] = False):
    task = transcript_file_task_add.delay(file.file, file.filename, current_user, srt, prompt)
    add_credit_record(task.id, current_user['sub'], file.filename, 'audio')
    return JSONResponse({"task_id": task.id})

@app.get("/tasks/{task_id}")
def get_status(task_id):
    task_result = celery.AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return JSONResponse(result)

@task_postrun.connect
def task_sent_handler(taskId, task, args, kwargs, retval, state, **extra_info):
    print('task_postrun for task id {taskId}', taskId)
