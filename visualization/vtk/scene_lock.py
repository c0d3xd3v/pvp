import functools
import threading

# VTK renders on Qt Quick's render thread while controllers change the scene on
# the GUI thread, and VTK releases the GIL inside its C++ calls, so both really
# run in parallel. Everything that touches the scene holds this lock.
SCENE_LOCK = threading.RLock()


def scene_locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with SCENE_LOCK:
            return fn(*args, **kwargs)
    return wrapper
