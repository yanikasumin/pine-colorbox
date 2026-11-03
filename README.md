# Colorbox — Gap Box Indicator for TradingView (Pine Script v6)

## Overview

A Pine Script v6 indicator for TradingView that detects price gaps, draws a box over each gap zone, and manages those boxes automatically. It is a single self-contained file, `colorbox.pine`, with no external dependencies. This is a chart-drawing indicator only: it does not place orders or execute trades.

## Features

- Gap detection: by default, the current candle is compared with the candle 2 bars back (bullish gap = current low above that candle's high; bearish gap = current high below that candle's low). A consecutive-candle comparison mode is also available.
- Automatic removal on fill: a box is deleted as soon as price trades back to the far edge of the zone and the gap is fully filled.
- Midline color change: when price first reaches the zone's 50% level (midline), the box fill color switches. The midline itself can optionally be drawn as a dashed line.
- Expiry: an unfilled box is deleted after a configurable number of bars (default 100).
- Box-count cap: the number of live boxes is capped (default 50); when the cap is reached, the oldest box is removed before a new one is created, so the cap is never exceeded, even temporarily.
- Size filter: a minimum gap size can be set in percent, price, or ATR multiples (ATR length default 14).
- Bar-close detection mode: an option to evaluate new-gap detection only on confirmed bar closes (recommended for alert use, since detection on a forming bar can repaint).
- Alerts: alert conditions for gap detection, midline touch, and gap filled.

## Usage

1. Open a chart on TradingView and open the Pine Editor at the bottom.
2. Delete any template code and paste the entire contents of `colorbox.pine`.
3. Click "Add to chart"; the indicator appears as "Colorbox".
4. Use the indicator's Settings (gear icon) to adjust the detection mode, minimum gap size, box lifetime and cap, and colors.
5. For alerts, pick one of the Colorbox alert conditions in TradingView's Alert dialog and set the frequency to "Once Per Bar Close".

## Main parameters

| Parameter | Default | Description |
|---|---|---|
| Gap measured between | Previous 2 candles | Choose "Previous 2 candles" or "Consecutive candles" |
| Show bullish / bearish gaps | Both on | Toggle each direction independently |
| Detect on bar close only | Off | When on, new-gap detection runs only at bar close |
| Minimum gap size (mode) | Percent | Percent, price, or ATR multiple |
| Minimum gap size (value) | 0 | 0 means every gap qualifies |
| ATR length | 14 | Used only in ATR-multiple mode |
| Delete unfilled box after | 100 bars | Counted from the gap candle |
| Maximum boxes on chart | 50 | The oldest box is removed first when the cap is reached |
| Draw midline | On | Dashed line at the zone's 50% level |

Colors (before/after midline touch, bullish/bearish, borders, midline) are also configurable.

## Tech stack

- Pine Script v6 (`//@version=6`), single file `colorbox.pine`
- Declared drawing caps: `max_boxes_count = 500` / `max_lines_count = 500`
- A Python logic mock, `mock/gap_logic_mock.py`, is included for verification (a re-implementation of the indicator's state machine)

## Tests

Pine Script cannot be compiled or run outside TradingView, so verification was done with the Python mock instead.

- Running `python3 mock/gap_logic_mock.py` checks 12 hand-built OHLC scenarios with known expected outcomes — bullish and bearish gap → midline touch → fill, expiry exactly at the configured bar count, minimum-gap-percent filtering, oldest-first eviction at the box cap, bar-close mode, midline and fill events on the same bar, the ATR threshold conditions, consecutive-candle mode, and a no-gap series — and all pass.
- The mock also validates its input data: every bar must satisfy `low ≤ open ≤ high` and `low ≤ close ≤ high`.
- For `colorbox.pine` itself, static checks were performed: bracket balance (with strings and comments stripped), absence of tabs, the version header, and a manual review of the built-in functions used.

## Verified scope & limitations

- **No TradingView compilation check has been performed.** In this environment the script was not pasted into the Pine Editor, compilation (free of errors and warnings) was not confirmed, and runtime behavior on a live chart was not observed. Before use, paste the script into TradingView's Pine Editor and confirm that it compiles.
- The Python mock verifies only the state transitions computed from confirmed (final) OHLC bars. It does not reproduce the tick-level behavior of Pine's `barstate.isconfirmed` gate on a forming bar (including drawing rollback); that remains unverified.
- Bar-close mode applies only to new-gap detection. Existing boxes are still evaluated on forming bars — fills, midline touches, and right-edge extension are processed on the forming bar — so bar-close mode does not make the indicator as a whole non-repainting.
- With live detection (bar-close mode off, the default), a box can appear intra-bar and disappear before the close (repainting). Results on historical bars are stable.
- Switching the chart timeframe recalculates everything from that timeframe's OHLC series, so the positions, number, and lifetimes of detected gaps depend on the timeframe.
- Bars are compared as consecutive bars of the chart series, including across session breaks (overnight, weekends, holidays); there is no session filter.
- On Heikin Ashi and other synthetic chart types, the script uses calculated display prices rather than traded prices, so detected gaps, midlines, and fills refer to those synthetic values.

---

## Development

This project was developed with AI assistance and went through multiple rounds of code review and revision. Detailed development notes are kept in `README.dev.md`.
