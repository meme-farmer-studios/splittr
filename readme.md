# splittr

simple gui wrapper around ffmpeg for audio splitting

## how to use

```
python splittr.py
# or py splittr.py if that's your jam (my personal fav)
```


requires ffmpeg/ffprobe on your system path and python3 with tk.

## features

- pick an input audio file (wav, mp3, flac, ogg, m4a, etc)
- pick an output folder
- enter a name prefix (e.g. "my audio - part ") and it will auto-add part number and source format (e.g. "my audio - part 12.wav")
- split by duration (hh:mm:ss segments) with live part count preview
- split into equal number of parts with live segment length preview
- live progress bar showing x/y parts and percentage (not really necessary since it's audio, it'll be done in a blink anyways but nice to have)

© meme farmer studios 2026