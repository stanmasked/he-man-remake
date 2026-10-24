"""Canonical Stage234 guest checkpoint sequence and conservative interpretation.

All descriptions are CPU/guest-written progress markers. None authenticates
that a GPU or genuine emulator executed the corresponding work.
"""
from __future__ import annotations

PHASES = (
    "01_nonce_validated",
    "02_shaders_loaded",
    "03_texture_upload_queue_idle",
    "04_upload_pixels_match",
    "05_render_commands_submitted",
    "06_render_queue_idle",
    "07_receipt_committed",
)

_DETAILS = (
    {
        "milestone": "guest_session_nonce_validated",
        "next_expected": "load_and_validate_shaders",
        "progress_interpretation": (
            "The guest reached nonce validation; no texture or render result is established."
        ),
    },
    {
        "milestone": "guest_shader_load_completed",
        "next_expected": "submit_texture_upload_and_wait",
        "progress_interpretation": (
            "The guest reports shader loading complete; texture upload and readback are not established."
        ),
    },
    {
        "milestone": "guest_texture_upload_queue_wait_returned",
        "next_expected": "read_back_and_compare_uploaded_texture",
        "progress_interpretation": (
            "The guest reports that the texture-upload queue wait returned; this does not attest device provenance."
        ),
    },
    {
        "milestone": "guest_upload_pixels_matched_synthetic_fixture",
        "next_expected": "record_and_submit_render_commands",
        "progress_interpretation": (
            "The guest reports a synthetic upload comparison passed; render submission has not yet been recorded."
        ),
    },
    {
        "milestone": "guest_render_commands_submitted",
        "next_expected": "wait_for_render_queue_idle",
        "progress_interpretation": (
            "The guest reached the post-submit checkpoint; queue completion, CPU readback, and receipt commit are not established."
        ),
    },
    {
        "milestone": "guest_render_queue_wait_returned",
        "next_expected": "cpu_readback_compare_and_commit_receipt",
        "progress_interpretation": (
            "The guest reports queue.waitIdle returned; the render readback, pixel comparison, and final receipt are not established."
        ),
    },
    {
        "milestone": "guest_final_receipt_checkpoint_written",
        "next_expected": None,
        "progress_interpretation": (
            "The guest reports its final receipt checkpoint; this is still not independent GPU execution or original iOS parity evidence."
        ),
    },
)

def describe_phase(phase: str) -> dict:
    """Return ordered progress metadata without treating a marker as attestation."""
    if not isinstance(phase, str):
        phase = ""
    try:
        index = PHASES.index(phase)
    except ValueError:
        return {
            "phase": phase or None,
            "known_phase": False,
            "phase_index": None,
            "milestone": None,
            "next_expected": None,
            "progress_interpretation": "Unknown phase; no progress stage can be inferred.",
            "runtime_gpu_execution_attested": False,
            "original_ios_graphics_parity_attested": False,
        }
    return {
        "phase": phase,
        "known_phase": True,
        "phase_index": index + 1,
        **_DETAILS[index],
        "runtime_gpu_execution_attested": False,
        "original_ios_graphics_parity_attested": False,
    }
