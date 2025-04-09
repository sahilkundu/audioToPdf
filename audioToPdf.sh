#!/bin/bash

# Supported media file extensions
exts=("wav" "mp3" "mp4" "mkv" "flac" "aac" "ogg" "webm" "m4a")

# Process all media files matching the supported extensions
for ext in "${exts[@]}"; do
    for file in *."$ext"; do
        [[ -f "$file" ]] || continue
        echo "🔊 Processing: $file"
        # Run transcription

        python3 audioToPdf.py

        
    done
done

echo "✅ All media files processed!"
