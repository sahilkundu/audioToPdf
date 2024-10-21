import os
import subprocess
import yt_dlp
import speech_recognition as sr
from pydub import AudioSegment
from fpdf import FPDF

def download_audio(youtube_url):
    print("Downloading audio...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'progress_hooks': [progress_hook],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    return 'audio.wav'

def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloaded {d['_percent_str']} of {d['filename']}")

def split_audio(wav_file, segment_length_ms=30000):  # Split into 30-second segments
    print("Splitting audio...")
    audio_segment = AudioSegment.from_wav(wav_file)
    segments = []
    
    for i in range(0, len(audio_segment), segment_length_ms):
        segment = audio_segment[i:i + segment_length_ms]
        segment_filename = f"audio_segment_{i // segment_length_ms}.wav"
        segment.export(segment_filename, format="wav")
        segments.append(segment_filename)
        print(f"Created segment: {segment_filename}")
    
    return segments

def transcribe_audio(wav_file):
    print("Transcribing audio...")
    recognizer = sr.Recognizer()
    segments = split_audio(wav_file)  # Split the audio into segments
    full_transcription = ""

    for i, segment in enumerate(segments):
        print(f"Transcribing segment {i + 1} of {len(segments)}: {segment}")
        with sr.AudioFile(segment) as source:
            audio_data = recognizer.record(source)

        try:
            # Detect language and transcribe audio
            text = recognizer.recognize_google(audio_data, show_all=False)
            full_transcription += text + " "  # Concatenate the transcriptions
            print(f"Transcribed segment {i + 1}: {text}")
        except sr.UnknownValueError:
            print(f"Audio segment '{segment}' not understood.")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service for segment '{segment}'; {e}")

    print("Transcription completed.")
    
    # Clean up temporary segments after transcription
    for segment in segments:
        if os.path.exists(segment):
            os.remove(segment)
            print(f"Removed temporary segment: {segment}")

    return full_transcription.strip()

def save_text_to_pdf(text, pdf_filename, wav_file):
    print("Saving transcription to PDF...")
    
    # Check if the file exists and rename if necessary
    base_filename, extension = os.path.splitext(pdf_filename)
    count = 1
    while os.path.exists(pdf_filename):
        pdf_filename = f"{base_filename}_{count}{extension}"
        count += 1
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    for line in text.splitlines():
        pdf.multi_cell(0, 10, txt=line)
    
    pdf.output(pdf_filename)
    
    # Clean up original audio file if it was newly downloaded
    if wav_file != 'audio.wav':
        os.remove(wav_file)
        print(f"Removed original audio file: {wav_file}")
        
    print(f"Saved PDF: {pdf_filename}")

def main():
    wav_file = 'audio.wav'

    # Check if the audio file already exists
    if os.path.exists(wav_file):
        print(f"Using existing audio file: {wav_file}")
    else:
        youtube_url = input("Enter the YouTube URL: ")
        # Download new audio if it doesn't exist
        wav_file = download_audio(youtube_url)

    transcription = transcribe_audio(wav_file)
    if transcription:
        pdf_filename = "transcription.pdf"
        save_text_to_pdf(transcription, pdf_filename, wav_file)

if __name__ == "__main__":
    main()
