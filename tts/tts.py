import io
import hashlib
import sys
from collections import OrderedDict

import soundfile as sf
import sounddevice as sd
from kokoro_onnx import Kokoro

# Kokoro
kokoro = Kokoro("models/kokoro-v1.0.int8.onnx", "models/voices-v1.0.bin")
voice = "af_heart"


class LimitedCache:
    """LRU cache with size and memory limits"""

    def __init__(self, max_items=100, max_memory_mb=50):
        self.max_items = max_items
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache = OrderedDict()
        self.current_memory = 0

    def _get_size(self, value):
        """Get approximate memory size of value in bytes"""
        if isinstance(value, bytes):
            return len(value)
        elif isinstance(value, tuple):
            # For samples cache: (samples, sample_rate)
            samples, _ = value
            return samples.nbytes if hasattr(samples, 'nbytes') else sys.getsizeof(samples)
        else:
            return sys.getsizeof(value)

    def get(self, key):
        """Get value and move to end (most recently used)"""
        if key in self.cache:
            value = self.cache[key]
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return value
        return None

    def put(self, key, value):
        """Put value in cache, evicting old items if necessary"""
        value_size = self._get_size(value)

        # If item already exists, remove it first
        if key in self.cache:
            old_value = self.cache[key]
            old_size = self._get_size(old_value)
            self.current_memory -= old_size
            del self.cache[key]

        # Evict items if we exceed limits
        while (len(self.cache) >= self.max_items or
               self.current_memory + value_size > self.max_memory_bytes) and self.cache:
            # Remove least recently used item
            oldest_key, oldest_value = self.cache.popitem(last=False)
            self.current_memory -= self._get_size(oldest_value)

        # Add new item
        self.cache[key] = value
        self.current_memory += value_size

    def __contains__(self, key):
        return key in self.cache

    def stats(self):
        """Get cache statistics"""
        return {
            'items': len(self.cache),
            'max_items': self.max_items,
            'memory_mb': round(self.current_memory / (1024 * 1024), 2),
            'max_memory_mb': round(self.max_memory_bytes / (1024 * 1024), 2)
        }


# Cache for storing samples (limit: 50 items, 50MB)
_samples_cache = LimitedCache(max_items=50, max_memory_mb=50)

print(kokoro.get_voices())


def play_audio(text, speed=1.1):
    # Create cache key
    cache_key = hashlib.md5(text.encode()).hexdigest()

    # Check cache first
    cached_samples = _samples_cache.get(cache_key)
    if cached_samples is not None:
        print(f"Cache hit for playback text: {text[:50]}...")
        samples, sample_rate = cached_samples
    else:
        # Generate samples if not in cache
        print(f"Cache miss, generating samples for playback text: {text[:50]}...")
        # append current time to text to avoid collision in cache during tests
        samples, sample_rate = kokoro.create(text, voice, speed=speed)
        # Store in cache
        _samples_cache.put(cache_key, (samples, sample_rate))
        print(f"Samples cache stats: {_samples_cache.stats()}")

    sd.play(samples, sample_rate, blocking=True, device=get_current_output_device())
    return None


def refresh_audio_devices():
    """Refresh the audio devices list to detect newly connected devices"""
    sd._terminate()
    sd._initialize()
    print("Audio devices refreshed")


def get_current_output_device():
    """Get the current default output audio device"""
    refresh_audio_devices()
    default_device = sd.default.device
    output_device = default_device[1]
    device = sd.query_devices(output_device)
    print('Current output device:', device['name'])
    return output_device


def test_sound(speed=1.1):
    text = "Hello, this is a test of the text to speech system."
    print("Playing audio...")
    import os
    if os.path.exists("audio.wav"):
        samples, sample_rate = sf.read('audio.wav', dtype='float32')
        print(f"Read back audio file with {len(samples)} samples at {sample_rate} Hz")
    else:
        print("Generating audio file...")
        samples, sample_rate = kokoro.create(text, voice, speed=speed)
        # sf.write('audio.wav', samples, sample_rate, format='wav')
        print(f"Generated audio with {len(samples)} samples at {sample_rate} Hz")
    sd.play(samples, sample_rate, blocking=True, device=get_current_output_device())
    print("Audio playback finished.")


if __name__ == '__main__':
    while True:
        start = input("Press Enter to play audio or type 'exit' to quit: ")
        if start.lower() == 'exit':
            break
        try:
            test_sound()
        except Exception as e:
            print("Error during audio playback:", e)
            pass
