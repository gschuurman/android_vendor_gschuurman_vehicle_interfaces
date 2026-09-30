Models preinstalled with Dicio (see `PreinstalledModels` in our Dicio build), installed to
`/product/usr/share/dicio` by device/khadas/vim3/car.mk, so voice works offline from the first boot:

- `vosk/vosk-model-small-en-us-0.15`, `vosk/vosk-model-small-nl-0.22`: Vosk speech recognition
  (Apache-2.0), unzipped from https://alphacephei.com/vosk/models/ — the models Dicio 4.0 downloads for
  English and Dutch. Another language: add its model (name as in Dicio's `VoskInputDevice.MODEL_URLS`).
- `openWakeWord/`: "Hey Dicio" wake word — melspectrogram.tflite and embedding.tflite (embedding_model)
  from openWakeWord v0.5.1 (Apache-2.0), wake.tflite = hey_dicio_v6.0.tflite from Dicio's v2.0 release.
- `whisper/ggml-base-q5_1.bin`: multilingual Whisper base model (MIT), 5-bit quantized ggml from
  https://huggingface.co/ggerganov/whisper.cpp — Dicio's default speech recognition when present: it
  transcribes commands in the app language and keeps words from other languages (song titles, place
  names) as they were said. ~1.4 s per command on the A311D (4 threads); Vosk remains selectable.
