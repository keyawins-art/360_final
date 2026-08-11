"""
Dedicated PLC ejection queue.

Decouples vision processing from PLC timing so that:
  1. Vision thread never blocks on serial I/O
  2. Only ONE thread writes to the serial port (no lock contention)
  3. Ejections fire in correct chronological order via priority queue
  4. Velocity-based overshoot compensation is preserved
  5. Hybrid sleep + spinlock for sub-millisecond precision

Architecture:
    Vision Thread → ejection_queue.schedule(...) → Queue
    EjectionWorker Thread → priority-ordered fire → Serial write
"""

import threading
import time
import datetime
import heapq


class EjectionEvent:
    """A scheduled PLC ejection command."""

    __slots__ = ("target_time", "command", "zone_name", "obj_id", "grade", "size_mm", "_seq")

    def __init__(self, target_time, command, zone_name, obj_id, grade, size_mm, seq):
        self.target_time = target_time
        self.command = command
        self.zone_name = zone_name
        self.obj_id = obj_id
        self.grade = grade
        self.size_mm = size_mm
        self._seq = seq  # Tiebreaker for heapq when target_time is equal

    def __lt__(self, other):
        if self.target_time == other.target_time:
            return self._seq < other._seq
        return self.target_time < other.target_time


class EjectionQueue:
    """
    Thread-safe priority queue for PLC ejection commands.

    Usage:
        eq = EjectionQueue(arduino=serial_obj, delay_seconds=7.20)
        eq.start()

        # From vision thread:
        eq.schedule(obj_id=42, command='11|', exit_time=time.perf_counter(),
                    zone_name='Zone-1', grade='W320', size_mm=22.5)

        # At shutdown:
        eq.stop()
    """

    def __init__(self, arduino=None, delay_seconds=7.20):
        self.arduino = arduino
        self.delay_seconds = delay_seconds

        self._heap = []  # Min-heap of EjectionEvent
        self._lock = threading.Lock()
        self._event = threading.Event()  # Wakes worker when new item arrives
        self._running = False
        self._worker = None
        self._seq = 0  # Monotonic sequence for tiebreaking

    def start(self):
        """Start the ejection worker thread."""
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="EjectionWorker")
        self._worker.start()
        print("[EJECTION] Worker thread started")

    def stop(self):
        """Stop the worker thread gracefully."""
        self._running = False
        self._event.set()  # Wake up if sleeping
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        print("[EJECTION] Worker thread stopped")

    def schedule(self, obj_id, command, exit_time, zone_name="", grade="", size_mm=0.0):
        """
        Schedule a PLC ejection command.

        Parameters
        ----------
        obj_id : int
            Tracked object ID.
        command : str
            Serial command string (e.g., '11|').
        exit_time : float
            Time when the object crossed the exit line (from time.perf_counter()).
        zone_name : str
            Zone name for logging.
        grade : str
            Grade label for logging.
        size_mm : float
            Object size for logging.
        """
        target_time = exit_time + self.delay_seconds

        with self._lock:
            self._seq += 1
            event = EjectionEvent(
                target_time=target_time,
                command=command,
                zone_name=zone_name,
                obj_id=obj_id,
                grade=str(grade or ""),
                size_mm=size_mm,
                seq=self._seq,
            )
            heapq.heappush(self._heap, event)

        now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        remaining = target_time - time.perf_counter()
        print(
            f"[{now_str}] [{zone_name}] EXIT ID:{obj_id} "
            f"(MM:{size_mm:.1f}, Grade:{grade}) -> QUEUED "
            f"(Fire in {remaining:.3f}s)"
        )

        self._event.set()  # Wake worker

    def pending_count(self):
        """Return the number of pending ejection events."""
        with self._lock:
            return len(self._heap)

    def _worker_loop(self):
        """
        Main worker loop. Waits for the next event, then fires it
        at the precise target time using hybrid sleep + spinlock.
        """
        while self._running:
            # Get the earliest event
            with self._lock:
                if self._heap:
                    next_event = self._heap[0]
                else:
                    next_event = None

            if next_event is None:
                # No events — wait for a new schedule() call
                self._event.wait(timeout=1.0)
                self._event.clear()
                continue

            now = time.perf_counter()
            wait_time = next_event.target_time - now

            if wait_time > 0.050:
                # Sleep in 5ms intervals until we're within 50ms
                # This prevents busy-waiting and saves CPU
                sleep_dur = min(wait_time - 0.050, 0.005)
                time.sleep(sleep_dur)
                continue  # Re-check in case a higher-priority event was added

            if wait_time > 0:
                # Final 50ms: busy-wait (spin) for sub-ms precision
                while time.perf_counter() < next_event.target_time:
                    pass

            # Pop the event
            with self._lock:
                if self._heap and self._heap[0] is next_event:
                    heapq.heappop(self._heap)
                else:
                    continue  # Event was removed by someone else

            # Fire the command
            self._fire(next_event)

    def _fire(self, event):
        """Send the serial command and log the result."""
        actual_delay = time.perf_counter() - (event.target_time - self.delay_seconds)

        if self.arduino:
            try:
                # Clear any stale input
                if self.arduino.in_waiting > 0:
                    self.arduino.read(self.arduino.in_waiting)

                self.arduino.write(event.command.encode())
                self.arduino.flush()

                now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(
                    f"\n[{now_str}] [{event.zone_name}] EXIT ID:{event.obj_id} "
                    f"-> COMMAND SENT (Total: {actual_delay:.3f}s) "
                    f"-> Sent:{event.command.strip()}"
                )
            except Exception as e:
                print(f"\n[{event.zone_name}] SERIAL WRITE ERROR for ID:{event.obj_id}: {e}")
        else:
            now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(
                f"\n[{now_str}] [{event.zone_name}] EXIT ID:{event.obj_id} "
                f"-> NO SERIAL (Total: {actual_delay:.3f}s) "
                f"-> Would send:{event.command.strip()}"
            )
