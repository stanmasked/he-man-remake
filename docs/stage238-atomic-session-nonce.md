# Stage238 — atomic, symlink-safe session nonce creation

## Change

Stage237 made PREPARE remove stale final/temporary capture, receipt and phase
files. Stage238 closes the remaining small filesystem gap in
\`run_nonce.txt\`: writing directly to a pre-existing symlink would follow
that symlink, and a partial write could leave a malformed request file.

PREPARE now removes stale \`run_nonce.txt.tmp\`, writes the complete new
nonce to that temporary file, and atomically replaces \`run_nonce.txt\` with
\`os.replace\`. Replacing an existing symlink replaces the link itself rather
than writing through it. On write/replace failure, PREPARE removes the temp
file and raises \`SessionError\`; it does not claim the session was prepared.

## Regression tests

- Seed a stale nonce temp and verify it is removed by PREPARE.
- Create \`run_nonce.txt\` as a symlink to a separate temporary test file.
- Run PREPARE and verify the SD path becomes a regular nonce file while the
  symlink target content remains unchanged.
- Verify the file content equals the new nonce and has the expected newline.

These are host-side filesystem tests with invented nonce/NRO data. They do
not execute or attest a Switch, emulator or GPU.

## Data policy

Only files under the dedicated synthetic \`switch/heman-stage230\` test
directory are cleaned or replaced. Original game data and unrelated files
are untouched. Raw captures and runner logs remain owner-private in Google
Drive; public CI uses fake fixtures only.
