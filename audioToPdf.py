import os
import yt_dlp
import speech_recognition as sr
from pydub import AudioSegment
from fpdf import FPDF
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from pydub.utils import mediainfo
import glob
import re
from pathlib import Path
import subprocess
import uuid
from urllib.parse import urlparse


def format_time(seconds):
    """Convert seconds to HH:MM:SS format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_audio_segments(wav_file, segment_length_ms):
    """Calculate number of segments based on audio length."""
    audio_info = mediainfo(wav_file)
    duration_sec = float(audio_info['duration'])
    total_segments = int(duration_sec * 1000 / segment_length_ms)
    print("========================================")
    print(f"File Name: {wav_file}")
    print(f"Audio Length: {format_time(duration_sec)}")
    print("========================================")
    return total_segments

def split_audio(wav_file, segment_length_ms):
    """Splits the audio file into user-defined segments."""
    print("Splitting audio...")
    # audio_segment = AudioSegment.from_wav(wav_file)
    audio_segment = AudioSegment.from_file(wav_file)
    segments = []
    
    for i in range(0, len(audio_segment), segment_length_ms):
        segment = audio_segment[i:i + segment_length_ms]
        segment_filename = f"{Path(wav_file).stem}_{i // segment_length_ms}.wav"
        segment.export(segment_filename, format="wav")
        segments.append((i // segment_length_ms, segment_filename))
    print(f"Please wait... We are uploading your file to the google server for transcribe.")
    return segments

def transcribe_segment(index, segment, total_segments,wav_file):
    """Transcribes a single audio segment."""
    recognizer = sr.Recognizer()
    with sr.AudioFile(segment) as source:
        audio_data = recognizer.record(source)
    
    try:
        # flac_data = audio_data.get_flac_data()
        # print(f"Estimated upload size for {(index + 1) / total_segments} : {len(flac_data) / (1024 * 1024):.2f} MB")
        text = recognizer.recognize_google(audio_data, show_all=False)
        completion = (index + 1) / total_segments * 100
        print(f"Transcribed segment {index + 1}/{total_segments} ({completion:.2f}%)")
        return index, text
    except sr.UnknownValueError:
        print(f"{Path(wav_file).stem} '{segment}' not understood.")
        return index, ""
    except sr.RequestError as e:
        print(f"Could not request results for '{segment}': {e}")
        return index, ""

def save_text_to_pdf(text_segments, pdf_filename, wav_file):
    print("Saving transcription to PDF...")

    base_filename, extension = os.path.splitext(pdf_filename)
    base_filename = re.sub(r"_\d+$", "", base_filename)  # Strip any existing _N suffix

    count = 1
    final_filename = f"{base_filename}.pdf"

    while os.path.exists(final_filename):
        final_filename = f"{base_filename}_{count}{extension}"
        count += 1

    # Create and save the PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for index, (start_time, segment_text) in enumerate(text_segments):
        pdf.multi_cell(0, 10, txt=f"[{format_time(start_time)}] {segment_text}")
        pdf.ln(5)

    pdf.output(final_filename)

    # if wav_file != 'audio.wav':
    #     os.remove(wav_file)
    #     print(f"Removed original audio file: {wav_file}")
    # Remove all segment files like audio_segment_0.*, audio_segment_1.*, etc.
    for segment_file in glob.glob(f"{Path(wav_file).stem}_*.*"):
        try:
            os.remove(segment_file)
            # print(f"Removed segment file: {segment_file}")
        except Exception as e:
            print(f"Error removing {Path(wav_file).stem}: {e}")

    try:
        original_path = Path(wav_file)
        done_path = Path("OriginalFiles") / (original_path.stem  + original_path.suffix)
        Path("OriginalFiles").mkdir(exist_ok=True)  # Create folder if not exists
        original_path.rename(done_path)
        print(f"Moved and renamed to: {done_path}")
    except Exception as e:
        print(f"Error moving/renaming file: {e}")


    print(f"Saved PDF: {final_filename}")

def transcribe_audio(wav_file, num_threads=4, segment_length=30):
    """Transcribes audio using multiple threads with user-defined segment length."""
    segment_length_ms = segment_length * 1000
    total_segments = get_audio_segments(wav_file, segment_length_ms)
    segments = split_audio(wav_file, segment_length_ms)
    
    transcriptions = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_to_segment = {executor.submit(transcribe_segment, index, seg, len(segments),wav_file): (index, seg) for index, seg in segments}
        
        for future in as_completed(future_to_segment):
            index, text = future.result()
            start_time = index * segment_length
            transcriptions.append((start_time, text))
    
    transcriptions.sort(key=lambda x: x[0])
    print("Transcription completed.")
    
    for _, segment in segments:
        if os.path.exists(segment):
            os.remove(segment)
    
    return transcriptions


def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloaded {d['_percent_str']} of {d['filename']}")

# def download_audio(youtube_url):
#     print("Downloading audio...")
    
#     ydl_opts = {
#         'format': 'bestaudio/best',
#         'outtmpl': 'audio.%(ext)s',
#         'postprocessors': [{
#             'key': 'FFmpegExtractAudio',
#             'preferredcodec': 'wav',
#             'preferredquality': '192',
#         }],
#         'progress_hooks': [progress_hook],
#     }
    
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         ydl.download([youtube_url])

#     return 'audio.wav'

def download_with_ffmpeg(url, mode='audio'):
    print(f"Downloading video+audio using FFmpeg...")

    output_name = f"ffmpeg_{mode}_{uuid.uuid4().hex[:8]}"
    # if mode == 'audio':
    #     output_file = f"{output_name}.wav"
    #     command = [
    #         "ffmpeg", "-y", "-i", url,
    #         "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", output_file
    #     ]
    output_file = f"{output_name}.mp4"
    command = ["ffmpeg", "-y", "-i", url, "-c", "copy", output_file]
    result = subprocess.run(command, capture_output=True)
    
    if result.returncode != 0:
        print("FFmpeg failed:", result.stderr.decode())
        return None

    return output_file

# def download_from_youtube(url):
#     print(f"Downloading video+audio from YouTube...")
#     ydl_opts = {
#         'format': 'bestvideo+bestaudio/best',
#         'outtmpl': 'youtube_video.%(ext)s',
#         'progress_hooks': [progress_hook],
#         }
#     output_filename = 'youtube_video.mp4'
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         ydl.download([url])

def download_from_youtube(url):
    print("Downloading video+audio...")

    # First, extract metadata to get the real title
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'youtube_video')
        ext = 'mp4'

    # Sanitize filename
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
    output_filename = f"{safe_title}.{ext}"

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{safe_title}.%(ext)s',
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_filename


    return output_filename
def is_streaming_url(url):
    return url.endswith(".m3u8") or url.endswith(".mpd")

def main():
    exts = ["wav", "mp3", "mp4", "mkv", "flac", "aac", "ogg", "webm", "m4a"]
    # wav_file = 'audio.wav'
    # Find any file with supported extension
    wav_file = None
    for ext in exts:
        matches = glob.glob(f"*.{ext}")
        if matches:
            wav_file = matches[0]
            break
    
    if not wav_file or not os.path.exists(wav_file):
        url = input("No supported media file found. Enter the video/audio URL: ").strip()
        # mode = input("Download audio or video? (audio/video, default audio): ").strip().lower() or 'audio'

        parsed = urlparse(url)
        # if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        #     wav_file = download_from_youtube(url, mode)
        # else:
        #     wav_file = download_with_ffmpeg(url, mode)

        # if not wav_file or not os.path.exists(wav_file):
        #     print("Download failed. Please check the URL and try again.")
        #     return
        if is_streaming_url(url):
            wav_file = download_from_youtube(url)
        elif "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
            wav_file = download_from_youtube(url)
        else:
            wav_file = download_from_youtube(url)  


    # if not os.path.exists(wav_file):
    #     youtube_url = input("Enter the Video URL: ")
    #     wav_file = download_audio(youtube_url)  # Ensure function exists
    
    segment_length = int(input("Enter segment length in seconds (default 30): ") or "30")
    # segment_length = 30

    # num_threads = int(input("Enter number of threads (default 4): ") or "4")
    num_threads = 200
    
    transcription = transcribe_audio(wav_file, num_threads, segment_length)
    if transcription:
        # save_text_to_pdf(transcription, "transcription.pdf", wav_file)
        save_text_to_pdf(transcription, f"transcription_{Path(wav_file).stem}.pdf", wav_file)


if __name__ == "__main__":
    main()
