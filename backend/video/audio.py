"""
Audio enhancement and background music mixing for the video pipeline.

Two responsibilities:

1. **enhance_voice_sync** — clean the original speech track: reduce steady
   background noise (denoise) and tame room echo / reverb tails (de-echo) so
   the voice is crisp. Runs early so silence detection, Whisper and the final
   render all benefit from clean audio.

2. **mix_music_sync** — mix a music track under the speech. Optional **ducking**
   lowers the music whenever the speaker talks (sidechain compression), so the
   voice stays intelligible — the standard "talking-head + music bed" feel.

All ffmpeg work is synchronous (run inside asyncio.to_thread from the pipeline).
"""
import os
import subprocess


def _run(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _has_audio_stream(path: str) -> bool:
    r = _run([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", path,
    ], timeout=30)
    return bool(r.stdout.strip())


def _build_enhance_chain(
    denoise: bool, dereverb: bool, rnnoise_model: str = "",
) -> str:
    """
    Compose the ffmpeg audio filter chain for voice cleanup.

    Order matters: cut rumble → denoise → de-echo (gate) → level → normalise.
    Uses only native ffmpeg filters so it works on any standard build; if an
    RNNoise model (.rnnn) is provided it replaces the spectral denoiser with a
    much stronger learned noise suppressor.
    """
    chain = [
        # Remove sub-bass rumble, mains hum and handling/AC noise below speech.
        "highpass=f=80",
    ]

    if rnnoise_model:
        # RNNoise: best free speech denoiser; also softens light reverb.
        model = rnnoise_model.replace("\\", "/")
        chain.append(f"arnndn=m='{model}'")
    elif denoise:
        # FFT spectral denoiser for steady hiss/hum + non-local-means cleanup.
        chain.append("afftdn=nf=-25:nr=12")
        chain.append("anlmdn=s=5")

    if dereverb:
        # A noise gate collapses the low-level reverb/echo tail that lingers
        # between words. `range` caps the attenuation so speech onsets don't
        # get chopped — gentle de-echo rather than a hard cut.
        chain.append(
            "agate=threshold=0.02:ratio=4:attack=10:release=200:range=0.1"
        )

    # Even out the dynamics, then normalise to the -16 LUFS social standard.
    chain.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=150:makeup=2")
    chain.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return ",".join(chain)


def enhance_voice_sync(
    video_path: str,
    output_path: str,
    denoise: bool = True,
    dereverb: bool = True,
    rnnoise_model: str = "",
) -> str:
    """
    Clean the speech audio of `video_path` → `output_path`.

    denoise       : reduce steady background noise (hiss, hum, AC, fans).
    dereverb      : tame room echo / reverb tails via a noise gate.
    rnnoise_model : optional path to an RNNoise .rnnn model — when set it
                    replaces the spectral denoiser with a learned one.

    The video stream is copied untouched (only audio is re-encoded), so this is
    fast. If the source has no audio track, the file is copied through verbatim.
    Returns output_path; raises on hard ffmpeg failure.
    """
    if not _has_audio_stream(video_path):
        _run(["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path])
        return output_path

    model = rnnoise_model if rnnoise_model and os.path.isfile(rnnoise_model) else ""
    af = _build_enhance_chain(denoise, dereverb, model)

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-af", af,
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        output_path,
    ]
    r = _run(cmd, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"voice enhance failed: {r.stderr[-400:]}")
    return output_path


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
