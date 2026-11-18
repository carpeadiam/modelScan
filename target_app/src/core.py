"""Small utility library used as the build/test target of the PipelineGuard experiments."""


def add(a, b):
    return a + b


def moving_average(values, window):
    if window <= 0:
        raise ValueError("window must be positive")
    return [sum(values[i - window + 1:i + 1]) / window for i in range(window - 1, len(values))]


def normalize_version(text):
    return tuple(int(p) for p in text.strip().lstrip("v").split("."))
