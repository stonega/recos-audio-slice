import logging
from typing import List, Dict

SrtItem = Dict[str, any]  # type: ignore
SrtTimestamp = str

def get_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(asctime)s: %(name)s  %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger

logger = get_logger(__name__)

def parse_srt(srt_string: str) -> List[SrtItem]:
    srt_lines = srt_string.strip().split("\n\n")
    srt_items = []
    for line in srt_lines:
        parts = line.strip().split("\n")
        start_time = parts[1].split(" --> ")[0]
        end_time = parts[1].split(" --> ")[1]
        srt_item = {
            "id": int(parts[0]),
            "time": parts[1],
            "start_time": start_time,
            "end_time": end_time,
            "text": "\n".join(parts[2:])
        }
        srt_items.append(srt_item)
    return srt_items


def convert_time_to_milliseconds(time_str: SrtTimestamp) -> int:
    hours, minutes, seconds = time_str.split(":")
    s, ms = seconds.split(",")
    return (
        int(hours) * 60 * 60 * 1000 +
        int(minutes) * 60 * 1000 +
        int(s) * 1000 +
        int(ms)
    )


def get_duration(start_time: SrtTimestamp, end_time: SrtTimestamp) -> int:
    start_milliseconds = convert_time_to_milliseconds(start_time)
    end_milliseconds = convert_time_to_milliseconds(end_time)
    return end_milliseconds - start_milliseconds


def merge_srt_strings(srt1: str, srt2: str) -> str:
    srt1_parsed = parse_srt(srt1)
    srt2_parsed = parse_srt(srt2)

    last_time_srt1 = srt1_parsed[-1]
    last_time_srt1["time"] = last_time_srt1["time"][:-6] + "00,000"

    time_parts = last_time_srt1["time"].split(" --> ")[1].split(":")
    end_time_srt1 = (int(time_parts[0]) * 3600 +
                     int(time_parts[1]) * 60) * 1000

    srt2_adjusted = []
    for subtitle in srt2_parsed:
        start, end = subtitle["time"].split(" --> ")
        parts = start.split(":")
        time_in_ms = (int(parts[0]) * 3600 + int(parts[1])
                      * 60 + float(parts[2].replace(",", "."))) * 1000
        adjusted_time = time_in_ms + end_time_srt1
        ms = int(adjusted_time % 1000)
        seconds = int((adjusted_time // 1000) % 60)
        minutes = int((adjusted_time // (1000 * 60)) % 60)
        hours = int((adjusted_time // (1000 * 60 * 60)))
        start_adjusted = f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"
        parts = end.split(":")
        time_in_ms = (int(parts[0]) * 3600 + int(parts[1])
                      * 60 + float(parts[2].replace(",", "."))) * 1000
        adjusted_time = time_in_ms + end_time_srt1
        ms = int(adjusted_time % 1000)
        seconds = int((adjusted_time // 1000) % 60)
        minutes = int((adjusted_time // (1000 * 60)) % 60)
        hours = int((adjusted_time // (1000 * 60 * 60)))
        end_adjusted = f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"
        srt2_adjusted.append({
            "id": subtitle["id"] + len(srt1_parsed),
            "time": f"{start_adjusted} --> {end_adjusted}",
            "text": subtitle["text"]
        })

    merged_subtitles = srt1_parsed + srt2_adjusted
    for i, subtitle in enumerate(merged_subtitles):
        subtitle["id"] = i + 1

    return "\n\n".join([f"{subtitle['id']}\n{subtitle['time']}\n{subtitle['text']}" for subtitle in merged_subtitles])


def merge_multi_srt_items(*items: SrtItem) -> SrtItem:
    start_time = items[0]["time"].split(" --> ")[0]
    end_time = items[-1]["time"].split(" --> ")[1]
    return {
        "id": items[0]["id"],
        "time": f"{start_time} --> {end_time}",
        "text": " ".join([item["text"] for item in items])
    }


def int_to_subtitle_time(seconds: float):
    hours = int(seconds // 3600)
    minutes = int((seconds // 60) % 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def merge_multiple_srt_strings(*srts: str) -> str:
    first_srt, *remaining_srts = srts
    merged_srt_string = first_srt
    for srt in remaining_srts:
        merged_srt_string = merge_srt_strings(merged_srt_string, srt)
    return merged_srt_string
