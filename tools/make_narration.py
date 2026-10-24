"""Generate one narration MP3 per video beat from docs/VIDEO_SCRIPT.md with edge-tts.

Skips beats whose narration starts with "(Ashwin" (recorded on camera). Output: video/narration/NN.mp3.
Usage: python tools/make_narration.py   (needs the edge-tts command on PATH)
"""
import subprocess
from pathlib import Path

VOICE = "en-US-AndrewMultilingualNeural"


def beats(script: str) -> list[tuple[str, str]]:
    rows = []
    for line in script.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0][:1].isdigit():
            rows.append((cells[0], cells[2]))
    return rows


def main() -> None:
    out = Path("video/narration")
    out.mkdir(parents=True, exist_ok=True)
    for i, (when, text) in enumerate(beats(Path("docs/VIDEO_SCRIPT.md").read_text(encoding="utf-8"))):
        if text.startswith("(Ashwin"):
            print(f"{i:02d} {when} skipped (on camera)")
            continue
        target = out / f"{i:02d}.mp3"
        subprocess.run(["edge-tts", "--voice", VOICE, "--rate=+8%", "--pitch=+2Hz", "--text", text,
                        "--write-media", str(target)], check=True)
        print(f"{i:02d} {when} -> {target}")


if __name__ == "__main__":
    main()
