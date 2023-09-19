from datetime import datetime
import io
import multiprocessing
import openai
import os
import uuid
from pytube import YouTube
from pydub import AudioSegment

from celery import Celery
from dotenv import load_dotenv
from tqdm import tqdm
import requests
from celery.signals import task_postrun

from database.database import get_user_credit, update_credit_record
from database.mongodb import get_subtitles_from_mongodb, save_subtitle_recos_to_mongodb, save_subtitle_result_to_mongodb, save_subtitle_summary_to_mongodb, update_subtitle_result_to_mongodb
from ai_request.recos import subtitle_recos
from ai_request.summary import subtitle_summary
from ai_request.translate import translate_gpt
from utils import int_to_subtitle_time, merge_multiple_srt_strings, parse_srt, logger
from faster_whisper import WhisperModel

load_dotenv()
celery = Celery('recos', broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379"),
                backend=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379"))
celery.conf.task_serializer = 'pickle'
celery.conf.result_serializer = 'pickle'
celery.conf.accept_content = ['application/json',
                              'pickle', 'application/x-python-serialize']

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
    logger.info('audio saved', filename,  end_time - start_time)
    return filename


def transcribe_audio(filename, format, prompt):
    logger.info(filename, format, prompt)
    with open(filename, "rb") as f:
        transcript = openai.Audio.transcribe(
            "whisper-1", f, api_key=OPENAI_API_KEY, response_format=format, prompt=prompt)
        # model_size = "medium"
        # model = WhisperModel(model_size, device='cpu',
        #                      compute_type="int8", download_root='/data')
        # segments, info = model.transcribe(f.name, beam_size=5)  # type: ignore
        # segments = list(segments)
        os.remove(filename)
        # result = []
        # for segment in segments:
        #     srt = f"{segment.id}" + '\n' + int_to_subtitle_time(segment.start) + \
        #         ' --> ' + int_to_subtitle_time(segment.end) + \
        #         '\n' + segment.text + '\n'
        #     result.append(srt)
        return transcript

def fix_subtitle(subtitle:str):
    prompt_text = f"""
    system_prompt = "You are a helpful assistant. Your task is to correct any spelling discrepancies in the transcribed text. Make sure only use the context provided
"""
    logger.info(prompt_text, subtitle)
    openai.api_key = os.getenv("OPENAI_API_KEY")
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {
                "role": "system",
                "content": prompt_text,
            },
            {
                "role": "user",
                "content": subtitle
            }
        ],
    )
    t_text = (
        completion["choices"][0]  # type: ignore
        .get("message")
        .get("content")
        .encode("utf8")
        .decode()
    )
    logger.info(t_text)
    return t_text


def get_youtube_audio_url(link):
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
        logger.info('youtube url', url)
        url = get_youtube_audio_url(url)
        logger.info('youtube audio url', url)
    logger.info('downloading:', url)
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
        logger.info('Audio downloaded')
        credit = get_user_credit(user['sub'])
        audio = AudioSegment.from_file(io.BytesIO(content))
        duration = round(len(audio) / ONE_MINUTE)
        if (duration > credit):
            return "Insufficient credit"
        format = 'srt' if srt else 'text'
        # Slice into max 5-minute chunks
        sliced_audios = slice_audio(audio, 10 * 60 * 1000)
        # Save files in /tmp
        files = []
        for audio in sliced_audios:
            logger.info(f'audio length:{len(audio)}')
            files.append(export_mp3(audio))
        # Transcribe
        results = []
        inputs = list(map(lambda file: (file, format, prompt), files))
        with multiprocessing.Pool(processes=len(inputs)) as pool:
            results = pool.starmap(transcribe_audio, inputs)
        update_credit_record(transcript_task_add.request.id,
                             user['sub'], -duration, len(audio), type)
        srts = parse_srt(merge_multiple_srt_strings(*results))  # type: ignore
        # Save subtitles
        save_subtitle_result_to_mongodb(srts, transcript_task_add.request.id)
        return
    else:
        transcript_task_add.update_state(
            state='FAILURE', meta={'exc': 'Failed to fetch audio'})


@celery.task(name="transcript-file.add")
def transcript_file_task_add(file: bytes, user, srt: bool = False, prompt: str = ''):
    credit = get_user_credit(user['sub'])
    audio = AudioSegment.from_file(io.BytesIO(file))
    duration = round(len(audio) / ONE_MINUTE)
    if (duration > credit):
        return 'Insufficient credit'
    format = 'srt' if srt else 'text'
    print('Audio length:', len(audio))
    # Slice into max 5-minute chunks
    sliced_audios = slice_audio(audio, 10 * 60 * 1000)
    # Export audio files
    files = []
    for audio in sliced_audios:
        logger.info(f'audio length: {len(audio)}')
        files.append(export_mp3(audio))
    results = []
    # Transcribe
    inputs = list(map(lambda file: (file, format, prompt), files))
    with multiprocessing.Pool(processes=len(inputs)) as pool:
        results = pool.starmap(transcribe_audio, inputs)
    # Update user credit
    update_credit_record(transcript_file_task_add.request.id,
                         user['sub'], -duration, len(audio), 'audio')
    srts = parse_srt(merge_multiple_srt_strings(*results))  # type: ignore
    # Save subtitles
    save_subtitle_result_to_mongodb(srts, transcript_file_task_add.request.id)
    print('Request sent')
    return


@celery.task(name="subtitles.translate")
def get_subtitles_translation(task_id, lang):
    result = get_subtitles_from_mongodb(task_id)
    subtitles = translate_gpt(result, lang)
    update_subtitle_result_to_mongodb(subtitles)
    return


@celery.task(name="subtitles.summary")
def get_subtitles_summary(task_id, lang):
    result = get_subtitles_from_mongodb(task_id)
    summary = subtitle_summary(result, lang)
    save_subtitle_summary_to_mongodb(summary, task_id)
    return


@celery.task(name="subtitles.recos")
def get_subtitles_recos(task_id):
    result = get_subtitles_from_mongodb(task_id)
    recos = subtitle_recos(result)
    save_subtitle_recos_to_mongodb(recos, task_id)
    return


@task_postrun.connect
def task_sent_handler(task_id, task, args, kwargs, retval, state, **extra_info):
    logger.info('task_postrun for task id {taskId}', task_id)
