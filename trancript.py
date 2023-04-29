from . import config

logger = config.get_logger(__name__)

@stub.function(
    image=app_image,
    shared_volumes={config.CACHE_DIR: volume},
    cpu=2,
)
def transcribe_segment(
    audio: bytes,
    model: config.ModelSpec
):
    import time
    import torch
    import whisper

    t0 = time.time()
    use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"
    model = whisper.load_model(
        Model.name, device=device, download_root=config.MODEL_DIR
    )
    result = model.transcribe(f.name, fp16=use_gpu)  # type: ignore

    logger.info(
        f"Transcribed segment {start:.2f} to {end:.2f} ({end - start:.2f}s duration) in {time.time() - t0:.2f} seconds."
    )

    # Add back offsets.
    for segment in result["segments"]:
        segment["start"] += start
        segment["end"] += start

    return result