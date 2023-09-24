"""
forked from https://github.com/rongjc/autosubtitle/blob/main/translate.py
"""
import ast
import os
import time
import openai
from utils import logger
from ai_request.utils import group_chunks, num_tokens_from_messages, supportedLanguages

def summary(text, output_locale):
    output_language = supportedLanguages[output_locale]
    prompt_text = f"You will be provided with podcast transcription, and your task is to summarize the podcast into a {output_language} text in about 50 words"
    print(prompt_text)
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {
                    "role": "system",
                    "content": prompt_text,
                },
                {
                    "role": "user",
                    "content":text 
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
        # format the translated text, the original text is eg: "\n\n['\\n柠檬\\n\\n', '梶井基次郎']", we need the
        # element in the list, not the \n \n

        try:
            t_text = ast.literal_eval(t_text)
        except Exception:
            # some ["\n"] not literal_eval, not influence the result
            pass
        # openai has a time limit for api  Limit: 20 / min
        time.sleep(3)
    except Exception as e:
        print(str(e), "will sleep 60 seconds")
        # TIME LIMIT for open api please pay
        time.sleep(60)
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {
                    "role": "user",
                    "content": prompt_text
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
        t_text = t_text.strip("\n")
        try:
            t_text = ast.literal_eval(t_text)
        except Exception:
            pass
    logger.info(t_text)
    return t_text


def subtitle_summary(subtitles, output_language):

    openai.api_key = os.getenv("OPENAI_API_KEY")
    ntokens = []
    chunks = []
    for subtitle in subtitles:
        chunk = subtitle['text']
        chunks.append(chunk)
        ntokens.append(num_tokens_from_messages(chunk))

    chunks = group_chunks(chunks, ntokens)
    summary_chunks = []
    for i, chunk in enumerate(chunks):
        print(str(i+1) + " / " + str(len(chunks)))
        summary_chunks.append(summary(chunk, output_language)+"\n")

    result = summary_chunks[0] if len(summary_chunks) == 1 else summary(
        "\n".join(summary_chunks), output_language)

    return result
