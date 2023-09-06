"""
Code from https://github.com/rongjc/autosubtitle/blob/main/translate.py
"""
import ast
import os
import time
import openai
import tiktoken


def group_chunks(chunks, ntokens, max_len=1000):
    """
    Group very short chunks, to form approximately a page long chunks.
    """
    batches = []
    cur_batch = ""
    cur_tokens = 0

    # iterate over chunks, and group the short ones together
    for chunk, ntoken in zip(chunks, ntokens):
        # print(ntoken)
        # notken = num_tokens_from_messages(chunk)
        cur_tokens += ntoken + 2  # +2 for the newlines between chunks

        # if adding this chunk would exceed the max length, finalize the current batch and start a new one
        if ntoken + cur_tokens > max_len:
            batches.append(cur_batch)
            cur_batch = chunk
            cur_tokens = 0
        else:
            cur_batch += "\n\n" + chunk
            # cur_batch += chunk
    batches.append(cur_batch)
    return batches


def num_tokens_from_messages(message, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo-0301":  # note: future models may deviate from this
        num_tokens = len(encoding.encode(message))
        return num_tokens
    else:
        raise NotImplementedError(f"""error.""")

def get_recos(text):

    prompt_text = f"""
I want you to extract info from text if any movies books you found.Return the item list split with \n, make sure not include any other text like The text mentions, Text:
{text}"""
    print(prompt_text)
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
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
            model="gpt-4",
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
    print(t_text)
    return t_text


def subtitle_recos(subtitles):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    ntokens = []
    chunks = []
    for subtitle in subtitles:
        chunk = subtitle['text']
        chunks.append(chunk)
        ntokens.append(num_tokens_from_messages(chunk))

    chunks = group_chunks(chunks, ntokens)
    recos_chunks = []
    for i, chunk in enumerate(chunks):
        print(str(i+1) + " / " + str(len(chunks)))
        recos_chunks.append(get_recos(chunk)+"\n")
    result = "\n".join(recos_chunks)

    return result
