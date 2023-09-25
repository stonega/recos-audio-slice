import ast
import time
import openai
from utils import logger, parse_srt
from ai_request.utils import group_chunks, num_tokens_from_messages


def fix(text):
    prompt_text="You will be provided with a subtitle content,  and your task is to combine two subtitle items if the item sentence is not complete.  Then correct any spelling discrepancies in the content. Then if the slash word is inside a url, convert it to /."
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
                    "content": text
                }
            ],
            temperature=0,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        t_text = (
            completion["choices"][0]  # type: ignore
            .get("message")
            .get("content")
            .encode("utf8")
            .decode()
        )

        try:
            t_text = ast.literal_eval(t_text)
        except Exception:
            pass
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
    return t_text


def fix_subtitle(subtitles):
    ntokens = []
    chunks = []
    for subtitle in subtitles:
        chunks.append(subtitle)
        ntokens.append(num_tokens_from_messages(subtitle))

    chunks = group_chunks(chunks, ntokens)
    fixed_chunks = []
    for chunk in enumerate(chunks):
        fixed_chunks.append(fix(chunk)+"\n")

    # join the chunks together
    result = '\n'.join(fixed_chunks)
    print(result)
    return parse_srt(result)
