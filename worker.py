from datetime import datetime
import io
import multiprocessing
from typing import BinaryIO
import openai
import os
import uuid
from pytube import YouTube
from pydub import AudioSegment

from celery import Celery
from dotenv import load_dotenv
from tqdm import tqdm
import requests

from credit import get_user_credit, update_credit_record, update_user_credit

load_dotenv()
celery = Celery('recos', broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379"), backend=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379"))
celery.conf.task_serializer = 'pickle'

ONE_MINUTE = 1000*60
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "_")
ALLOWED_EXTENSIONS = {'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'}

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
def export_mp3(audio):
    start_time = datetime.now()
    filename = '/tmp/' + str(uuid.uuid4()) + '.mp3'
    audio.export(filename, format="mp3")
    end_time = datetime.now()
    print('Audio saved', filename,  end_time - start_time, sep="---")
    return filename
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

@celery.task(name="transcript.add")
def transcript_task_add(url: str, user, title: str = '', srt: bool = False, prompt: str = '', type: str = 'audio'):
    if (type == 'youtube'):
        print('Youtube url', url)
        url = get_youtube_audio_url(url)
        print('Youtube audio url', url)
    print('Downloading:', url)
    print('Srt format', srt)
    try:
        response = requests.get(url, stream=True)
    except requests.exceptions.HTTPError as err:
        return 'Failed to fetch url'

    total_size = int(response.headers.get('content-length', 0))

    # Initialize the bytearray
    content = bytearray()

    for data in tqdm(response.iter_content(chunk_size=1024 * 1024), total=total_size // 1024 / 1024, unit='MB', unit_scale=True):
        content.extend(data)

    if response.status_code == 200:
        print('Audio downloaded')
        credit = get_user_credit(user['sub'])
        audio = AudioSegment.from_file(io.BytesIO(content))
        duration = round(len(audio) / ONE_MINUTE)
        if (duration > credit):
            return "Insufficient credit"
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
        update_credit_record( transcript_task_add.request.id, user['sub'], -duration, len(audio), type)
        return results
    else:
        return 'Failed to fetch url'

@celery.task(name="transcript-file.add")
def transcript_file_task_add(file: BinaryIO, filename: str, user, srt: bool = False, prompt: str = ''):
    if file and allowed_file(filename):
        credit = get_user_credit(user['sub'])
        backend_api = os.environ.get('BACKEND_API', '_')
        audio = AudioSegment.from_file(file)
        duration = round(len(audio) / ONE_MINUTE)
        if (duration > credit):
            return 'Insufficient credit'
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
        update_user_credit(user['sub'], -duration, len(audio), filename, 'audio')
        print('Request sent')
        return results
    else:
        return 'File not allowed'