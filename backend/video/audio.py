"""
Background music mixing for the video pipeline.

Mixes a music track under the original (speech) audio. Optional **ducking**
lowers the music whenever the speaker talks (sidechain compression), so the
voice stays intelligible — the standard "talking-head + music bed" feel.

All ffmpeg work is synchronous (run inside asyncio.to_thread from the pipeline).
Opt-in: the pipeline only calls it when music is configured.
"""
import subprocess


def _run(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _has_audio_stream(path: str) -> bool:
    r = _run([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", path,
    ], timeout=30)
    return bool(r.stdout.strip())


def mix_music_sync(
    video_path: str,
    output_path: str,
    music_path: str,
    music_volume: float = 0.18,
    ducking: bool = True,
) -> str:
    """
    Mix `music_path` under the audio of `video_path` → `output_path`.

    music_volume : 0..1 baseline music level (0.18 ≈ subtle bed).
    ducking      : if True, music drops under speech via sidechaincompress.

    If the source has no audio track, the music simply becomes the soundtrack.
    Returns output_path; raises on hard ffmpeg failure.
    """
    vol = max(0.0, min(1.0, music_volume))
    has_voice = _has_audio_stream(video_path)

    # Music is looped to outlast the video, then trimmed by -shortest.
    base = ["ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", music_path]

    if not has_voice:
        fc = f"[1:a]volume={vol}[aout]"
    elif ducking:
        fc = (
            f"[1:a]volume={vol}[mraw];"
            "[0:a]asplit=2[voice][key];"
            "[mraw][key]sidechaincompress="
            "threshold=0.03:ratio=8:attack=20:release=400:makeup=1[mduck];"
            "[voice][mduck]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        fc = (
            f"[1:a]volume={vol}[m];"
            "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )

    cmd = base + [
        "-filter_complex", fc,
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-shortest", output_path,
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"music mix failed: {r.stderr[-400:]}")
    return output_path
