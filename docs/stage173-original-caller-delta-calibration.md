# Stage173 — original gameplay caller delta-time calibration

The original iOS v2.0.0 IPA was fetched from the owner's Google Drive
into a private working environment. No IPA bytes, executable, raw
disassembly, original resources or private reports are uploaded here.

## Recovered call path

Independent ARMv7 inspection of the owner's binary established the
following control/data path:

1. HeloApp::_tick obtains a time value separately for the application's
   timestamp state, then supplies the exact float32 bit pattern
   0x3d23d70a (0.04f) as the float argument to its application-handler
   callback.
2. GSAppDelegate::onTick receives that float, preserves it as a
   float32 value and forwards it to Kernel::tick.
3. Kernel::tick forwards the same delta to GOManager::tick; the manager
   passes it through the game-object-group update path.
4. CSprite::tick(float, int) forwards its float delta to
   SpritePlayer::tick(float).
5. SpritePlayer::tick(float) multiplies the input by its custom
   animation rate, then by 1000.0f, and converts to signed integer
   with truncation toward zero before calc(int).

At the default SpritePlayer animation rate 1.0f, an input 0.04f
produces a 40-unit integer increment. This is consistent with a
seconds-to-milliseconds conversion for the per-player animation clock.

## Important unresolved scheduling discrepancy

The same binary's GSAppDelegate::onCreate calls HeloApp::setTimer(60).
HeloTimeDelegate::setTimer converts that frequency to a nominal
1/60-second timer interval. GSAppDelegate::onTick also maintains a
separate wall-clock accumulator and applies 16-ms threshold/subtraction
logic around calls into Kernel::tick.

Thus the scalar handed to the player is **fixed at 0.04f on this
path**, while the scheduling infrastructure has a nominal 60-Hz timer
and its own elapsed-time accumulator. These facts must not be collapsed
into the claim that the complete gameplay loop runs at 25 Hz or 60 Hz.
The effective relationship among timer callbacks, accumulator catch-up,
gameplay steps and animation progression needs a deterministic caller
trace to reconcile it fully.

## Stage173 changes

The synthetic Switch clock probe now uses the observed 0.04f input per
simulation step, while retaining its separate 60-Hz host loop interval.
The host C99 tests verify the 40-unit step and a complete fabricated
finite-replay sequence under that input. The test is explicitly a
reproduction of the observed *argument value*, not proof of effective
wall-clock game speed.

No production game NRO, main branch, actor state, sprite atlas or
original art is modified. The probe remains asset-free.

## Next proof obligation

Instrument or statically reconcile the GSAppDelegate wall-clock
accumulator, its 16-ms catch-up loop and the fixed 0.04f argument
through Kernel::tick and SpritePlayer::tick. Compare predicted update
counts over a known elapsed interval before changing the production
Switch animation clock or claiming frame-rate parity.
