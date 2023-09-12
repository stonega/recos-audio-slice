"""
forked from https://github.com/rongjc/autosubtitle/blob/main/translate.py
"""
import ast
import os
import time
import openai
import tiktoken
import re
def group_chunks(chunks, ntokens, max_len=2000):
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

def num_tokens_from_messages(message, model="gpt-3.5-turbo-16k"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(message))
    return num_tokens


def translate(text,output_language):
    
    prompt_text = f"""
Task: Extract subtitle text, and translate to {output_language}, then translated sentences must have the same timestamp with provided subtitle, especially the last one. Provide your response with subtitle format.
Text to translate:
{text}"""
    print(prompt_text)
    
    try:
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
            completion["choices"][0] # type: ignore
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
            completion["choices"][0] # type: ignore
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

def translate_gpt(subtitles, output_language):
    
    openai.api_key = os.getenv("OPENAI_API_KEY")
    ntokens = []
    chunks = []
    for subtitle in subtitles:
        chunk = str(subtitle['start_time'] + '-->' + subtitle['end_time'] + '\n' + subtitle['text'])
        chunks.append(chunk)
        ntokens.append(num_tokens_from_messages(chunk))
    
    chunks = group_chunks(chunks, ntokens)
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        print(str(i+1) + " / " + str(len(chunks)))
        translated_chunks.append(translate(chunk, output_language)+"\n")
    
    # join the chunks together
    result = '\n'.join(translated_chunks)
    data = []
    pattern = r'(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\n(.+?)\n'
    matches = re.findall(pattern, result, re.DOTALL)
    for match in matches:
        data.append(match[1])
    
    for index, subtitle in enumerate(subtitles):
        if index < len(data):
            subtitle['default_translation_text'] = data[index]
    print(result, matches, data)
    return subtitles 
