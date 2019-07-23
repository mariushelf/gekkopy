import numpy as np


def create_windows(df, window_size, step_size=1, target=None) -> np.array:
    if target:
        t_col = df[target].values
        df = df.drop(target, axis=1)
    v = df.values
    n = v.shape[0]
    i = 0
    windows = []
    t = []
    while i + window_size < n:
        windows.append(v[i : i + window_size, :])
        if target:
            t.append(t_col[i + window_size - 1])
        i += step_size
    windows = np.array(windows)
    t = np.array(t).reshape(-1, 1)
    if target:
        return windows, t
    else:
        return windows
