# Stage225 — NeXium padded-PNG guest framebuffer proof

Stage224 cross-compiled a synthetic libnx NRO and tested its portable C99 uploader
on the host. Stage225 establishes a separate genuine guest execution gate.
This remains a libnx CPU/software-framebuffer probe, not deko3d GPU sampling
or an original iOS gameplay frame.

The new workflow cross-builds the optional Stage224 heman_png_padding_probe.nro
using devkitPro and checks the AArch64 ELF and NRO0 signatures.
It checks out the pinned NeXium commit
b6149f647f1b0824e450555beb6cfc16b6f0e075, applies the existing
NRO file-origin patch, and instruments the production guest frame receiver.
It runs the real NRO under the rustarmic CPU backend and requires a successful
guest exit, actual guest CPU instructions/SVCs and at least 300 frames.
The verifier then requires native guest framebuffer PNGs from frames 30, 120,
and 300 with 640x360 dimensions.

Both the existing Stage209 synthetic checkerboard and 16 independent Stage224
padded-RGB panel pixel samples must match at each guest frame. These include
the right padded column and bottom padded rows, which are black. Background
checks and earlier checkerboard checks must continue to pass.

The workflow preserves short-lived PNG/log/hash evidence; it does not access
the user's original IPA, source texture PNGs or private offsets. The verifier
is separately tested against invented good and bad captures, including
missing frames, incorrect padded pixels, incorrect old checker pixels,
unexpected dimensions and non-PNG data.

A passing workflow would establish synthetic software-framebuffer pixels
from *actual emulated guest execution*, not GPU texture filtering, hardware
Switch output or original iOS screen/camera parity. Neither successful host
tests nor successful NRO cross-compilation substitute for runtime evidence.
