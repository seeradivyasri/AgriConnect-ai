from faster_whisper import WhisperModel
import time

def main():
    print("Downloading/loading Faster-Whisper 'small' model...")
    start_time = time.time()
    
    # Instantiating the model will automatically download the weights from HuggingFace
    # into the local cache directory if they don't already exist.
    model = WhisperModel("small", device="cpu", compute_type="int8")
    
    elapsed = time.time() - start_time
    print(f"Whisper small ready. (Took {elapsed:.2f} seconds)")

if __name__ == "__main__":
    main()
