import csv
import time
from typing import Iterator, Dict, Any, Iterable

class DataStream:
    """Base interface for all data streams."""
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError


class CSVStream(DataStream):
    """
    Reads a CSV file line by line, simulating a data stream.
    Expected NAB format: timestamp, value, label (optional)
    """
    def __init__(self, file_path: str, loop: bool = False, delay_seconds: float = 0.0):
        """
        Args:
            file_path: Path to the CSV file.
            loop: If True, restarts the stream from the beginning when EOF is reached.
            delay_seconds: Artificial delay between yielding points.
        """
        self.file_path = file_path
        self.loop = loop
        self.delay_seconds = delay_seconds

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        while True:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean keys, as sometimes headers have variations
                    row_clean = {k.strip().lower(): v for k, v in row.items() if k}
                    
                    if 'timestamp' not in row_clean or 'value' not in row_clean:
                        continue
                        
                    is_anomaly = False
                    # NAB typically uses 'label'
                    if 'label' in row_clean:
                        is_anomaly = str(row_clean['label']).strip() == '1'
                    elif 'is_anomaly' in row_clean:
                        val = str(row_clean['is_anomaly']).strip().lower()
                        is_anomaly = val in ('1', 'true')
                        
                    try:
                        value = float(row_clean['value'])
                    except ValueError:
                        continue # Skip malformed rows
                        
                    yield {
                        "timestamp": row_clean["timestamp"],
                        "value": value,
                        "is_anomaly": is_anomaly
                    }
                    
                    if self.delay_seconds > 0:
                        time.sleep(self.delay_seconds)
            
            if not self.loop:
                break


class KafkaStubStream(DataStream):
    """
    Stub for a Kafka consumer. Exposes the exact same iterator interface as CSVStream.
    Instead of connecting to a real broker, it consumes from a provided underlying iterable
    (like CSVStream or generate_synthetic_stream).
    
    This conforms to CLAUDE.md Section 8 and PRD Section 8, ensuring the Kafka stub
    can be swapped with a real Kafka client later without changing downstream consumers.
    """
    def __init__(self, topic: str, source_iterable: Iterable[Dict[str, Any]]):
        """
        Args:
            topic: The Kafka topic to subscribe to (ignored in stub).
            source_iterable: The underlying iterable to pull messages from (for simulation).
        """
        self.topic = topic
        self.source_iterable = source_iterable

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """
        Polls the stubbed source stream and yields records in the exact same shape.
        """
        for record in self.source_iterable:
            # A real Kafka consumer would deserialize messages here.
            # For the stub, we just yield the record from the simulation.
            yield record
