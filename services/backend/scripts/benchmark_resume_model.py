"""Synthetic CPU smoke measurement, not a matching-quality benchmark."""

import argparse
import json
import sys
import time


def peak_mib():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in [
                    "peak",
                    "working",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                ]
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return None
        return counters.peak / 1024**2
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024**2 if sys.platform == "darwin" else 1024)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    from app.nlp.cpu_embedding import CpuEmbeddingClient

    encoder = CpuEmbeddingClient(args.model_dir)
    loaded = time.perf_counter()
    texts = ["Python developer", "Python engineer", "Cooking food", "Python " * 700 + "SQL " * 300]
    batch = encoder.embed(texts)
    end = time.perf_counter()
    print(
        json.dumps(
            {
                "model_revision": batch.model_revision,
                "dimensions": batch.dimensions,
                "texts": len(texts),
                "load_seconds": round(loaded - start, 3),
                "batch_seconds": round(end - loaded, 3),
                "peak_process_mib": peak_mib(),
                "scope": "Synthetic single-process CPU smoke; not cloud or quality evidence",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
