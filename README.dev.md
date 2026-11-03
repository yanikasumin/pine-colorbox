# Colorbox — Gap Box Indicator (TradingView / Pine Script v6)

A single, self-contained Pine Script indicator that detects price gaps,
draws a box over each gap zone, and manages the boxes automatically:

- the box is **deleted as soon as the gap is fully filled**,
- the box **changes color when price reaches the gap's midline** (50% level),
- an unfilled box is **deleted after a configurable number of bars**,
- the number of boxes on the chart is capped; the oldest box is removed
  *before* a new one is created, so the configured cap (at most 500) is
  not exceeded even temporarily.

File: **`colorbox.pine`** (Pine Script **v6**, no external dependencies).

---

## How to install on TradingView

1. Open a chart on TradingView and click **Pine Editor** at the bottom.
2. Delete any template code, then paste the entire contents of
   `colorbox.pine`.
3. Click **Add to chart**. The indicator appears as "Colorbox".
4. Open the indicator's **Settings** (gear icon) to adjust the parameters
   described below.
5. Optional: use TradingView's **Alert** dialog and pick one of the four
   "Colorbox: …" alert conditions (gap detected / midline touched / gap
   filled). Set the alert frequency to **Once Per Bar Close** (see
   "Alerts and repainting" below).

---

## What counts as a gap

Default definition ("Previous 2 candles"):
the current candle is compared with the candle **2 bars back**.

- **Bullish gap (gap up):** current low > high of the candle 2 bars back.
  The box spans from that high (bottom) to the current low (top).
- **Bearish gap (gap down):** current high < low of the candle 2 bars back.
  The box spans from the current high (bottom) to that low (top).

The box's left edge starts at the older candle of the pair and the box
extends to the right, bar by bar, until it is filled or expires.

A gap is **filled** when price trades back to the far edge of the zone
(for a bullish gap: a later candle's low reaches the zone's bottom; for a
bearish gap: a later candle's high reaches the zone's top). The **midline**
is the 50% price level of the zone.

With **Detect on bar close only** enabled, detection runs on the newer
candle's confirmed close (`barstate.isconfirmed`) using that candle's final
high/low — and the ATR of that same candle when ATR mode is used. There is
no one-bar detection delay: a gap is registered on the bar that forms it,
and if the following bar fills it, the box is removed on that following bar.

### Chart-data behavior

- **Session boundaries:** bars are compared as consecutive bars of the
  chart series, including across session breaks (overnight, weekends,
  holidays). The first bar of a new session is compared with the last bars
  of the previous session; there is no session filter.
- **Non-standard chart types:** the script uses the chart's OHLC values as
  provided. On Heikin Ashi and other synthetic chart types those values are
  calculated display prices, not traded exchange prices, so detected gaps,
  midlines, and fills refer to the synthetic values.
- **Timeframe changes:** switching the chart timeframe recalculates
  everything from that timeframe's bars, so the detected gaps can differ.

### Alerts and repainting

With bar-close detection **off** (the default), detection uses the forming
candle: a box can appear intra-bar and disappear again before the bar
closes if the gap closes up — that is repainting, and an alert that has
already been sent cannot be retracted. For alert use, set the alert
frequency to **Once Per Bar Close**. Enabling **Detect on bar close only**
additionally ensures that gap *detection* itself only ever uses final,
closed-candle values.

## Parameters

### 1. Detection
| Parameter | Default | Meaning |
|---|---|---|
| Gap is measured between | Previous 2 candles | "Previous 2 candles" or "Consecutive candles" (current vs. immediately previous candle). |
| Show bullish gaps | on | Toggle gap-up boxes. |
| Show bearish gaps | on | Toggle gap-down boxes. |
| Detect on bar close only | off | On: **new-gap detection only** is evaluated at the newer candle's confirmed close, using its final values (no one-bar delay). Existing boxes are still managed in real time on the forming bar (fill / midline / extension), so the indicator as a whole does not wait for the bar close. Off: detection is live on the forming candle (can repaint — see "Alerts and repainting"). |
| Minimum gap size — mode | Percent | Unit of the threshold: Percent / Price / ATR multiple. |
| Minimum gap size — value | 0 | Gaps smaller than this are ignored. 0 = every gap qualifies in every mode (in ATR mode the threshold is then exactly 0, even before the ATR is available). Percent is relative to the absolute value of the older candle's edge price, so the threshold stays positive even on negative-priced series. With a positive ATR multiple, gaps are not evaluated until the ATR has enough history. |
| ATR length | 14 | Only used in ATR-multiple mode. |

### 2. Box lifetime
| Parameter | Default | Meaning |
|---|---|---|
| Delete unfilled box after (bars) | 100 | Unfilled boxes are removed once this many bars have passed since the gap candle. |
| Maximum boxes on chart | 50 | Cap on live boxes; when the cap is reached, the oldest box is removed *before* a new box is created, so the cap is never exceeded, even temporarily. (Hard drawing caps of 500 boxes / 500 lines are also declared in the script.) |

### 3. Style
| Parameter | Default | Meaning |
|---|---|---|
| Bullish gap — fill | green, 85% transp. | Box fill before the midline is touched. |
| Bullish gap — fill after midline | teal, 70% transp. | Box fill after the midline is touched. |
| Bearish gap — fill | red, 85% transp. | Same, for gap-down boxes. |
| Bearish gap — fill after midline | orange, 70% transp. | Same, after midline touch. |
| Bullish / bearish gap — border | green / red, 40% transp. | Box border colors. |
| Draw midline | on | Draws a dashed line at the 50% level inside each box. |
| Midline color | gray | Color of the midline. |

---

## Feature coverage

| Feature | Implementation |
|---|---|
| Detect gaps from the previous 2 candles | Default gap mode compares the current candle with the candle 2 bars back (both directions). A consecutive-candle mode is included as an option. |
| Draw a box over the gap zone | One box per gap, spanning the full gap zone, extended right on every bar while the gap is open. |
| Delete the box when the gap is filled | Fill = price reaches the far edge of the zone; the box (and its midline) is deleted on that bar. |
| Color change via the midline | When price first reaches the 50% midline, the fill color switches to the "after midline" color. The midline itself is drawn (optional) as a dashed line. |
| Delete after a set number of bars if unfilled | "Delete unfilled box after (bars)" input (default 100). |
| Threshold / size filter | Minimum gap size in Percent, absolute Price, or ATR multiples. |
| Box-count management | "Maximum boxes on chart" input; the oldest box is evicted before a new box is created when the cap is reached, plus `max_boxes_count = 500` / `max_lines_count = 500` declarations. |

## Verification performed

Pine Script cannot be compiled or run outside TradingView, so verification
was done in two layers:

1. **Logic mock (executable).** The indicator's state machine is mirrored
   in Python (`mock/gap_logic_mock.py`, included in this folder) with the
   same per-bar order of operations (manage → detect, with cap eviction
   before creation). Twelve hand-built OHLC scenarios with known expected
   outcomes all pass:
   bullish gap → midline touch → fill; bearish gap → midline touch → fill;
   expiry exactly at the configured bar count; minimum-gap-percent
   filtering; oldest-first eviction at the box cap (eviction event ordered
   before creation); **bar-close mode: a gap filled on the bar after it
   forms does not linger**; **midline and fill events on the same bar**;
   **ATR threshold taken from the gap bar itself**; **ATR multiple 0
   qualifying before the ATR is available**; **a positive ATR multiple
   waiting for the ATR**; consecutive-candle mode; and a no-gap series
   producing no boxes.
   Run it with: `python3 mock/gap_logic_mock.py` → `ALL TESTS PASSED`.
   The mock also validates its input data: every bar must satisfy
   `low ≤ open ≤ high` and `low ≤ close ≤ high`, as real OHLC data does.
   **Scope of the mock's verification:** the mock verifies the state
   transitions computed from *confirmed (final) OHLC bars*. Its
   `confirm_bar` flag does not change the mock's arithmetic — in a
   bar-level model both settings evaluate the same final values — so the
   mock does **not** verify the tick-level behaviour of Pine's
   `barstate.isconfirmed` gate on a forming bar (including drawing
   rollback). That gate is a TradingView manual-check item, like
   compilation itself (see "Not verified" below).
2. **Static checks of `colorbox.pine`.** Bracket balance
   (strings/comments stripped), absence of tabs, the `//@version=6`
   header, and a manual review of the built-ins used
   (`box.new/delete/set_right/set_bgcolor`, `line.new/delete/set_x2`,
   `array.*`, `ta.atr`, `barstate.isconfirmed`, `alertcondition`, UDT
   field order in `GapBox.new`).

**Not verified — TradingView compilation:** Pine Script cannot be compiled
outside TradingView, and **no TradingView compile check has been performed
in this environment**. The script has not been pasted into the Pine Editor,
and no runtime behavior on a live chart has been observed. The logic
results above come from the Python mirror of the same rules, not from
TradingView itself. The outstanding manual checks on TradingView are:
compile with no errors or warnings; bar-close detection on a live bar
(no box while the bar is forming, box appears at the close); live-mode
appearance/disappearance of boxes; fill, midline, and expiry behaviour;
and the four alert conditions firing. The compile check remains an
outstanding step: paste the script into TradingView's
Pine Editor (install step 2 above) and confirm it compiles and displays
as expected.

## Interpretation choices

These choices were made where the requirements were ambiguous; all of
them can be changed quickly if a different reading is intended:

1. **Gap pair.** "Previous 2 candles" is implemented as *current candle vs.
   the candle 2 bars back* (the in-between candle is spanned by the box).
   Note that this three-candle pattern is closer to a Fair Value Gap (FVG)
   than to a simple two-candle price window. If *the last two consecutive
   candles* are meant instead (a simple window between adjacent candles),
   the "Consecutive candles" mode already covers it — one input switch.
2. **"Filled"** is implemented as a *full* fill (price reaches the far edge
   of the zone). If a *partial* fill (e.g. 50%) should already remove or
   shrink the box, that is a small change.
3. **Midline color change** triggers on the *first touch* of the 50% level
   while the gap is being filled. An alternative reading — color depending
   on whether the current price is above/below the midline — is not
   implemented.
4. **Expiry counting** starts at the gap candle itself; the box is removed
   on the bar where the elapsed count reaches the setting.
5. **Live-bar behavior.** With "Detect on bar close only" off (default),
   a box can appear intra-bar on the forming candle and can disappear
   again before the close (repainting); on historical bars the results are
   stable. For alerts, use the **Once Per Bar Close** frequency. See
   "Alerts and repainting" and "Chart-data behavior" (session boundaries,
   synthetic chart types) above.
