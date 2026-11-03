#!/usr/bin/env python3
"""
Logic mock of the Colorbox Pine Script indicator (colorbox.pine).

Pine Script cannot be executed locally, so the gap-box state machine is
re-implemented here with the Pine version's per-bar order of operations:

    for each bar:
        1) manage existing boxes (record a first midline touch before any
           deletion, then fill -> delete or expiry -> delete; otherwise
           recolor on a midline touch and keep the box open)
        2) detect a new gap (newer candle = current bar,
           older candle = bar[span]); before creating its box, evict the
           oldest box whenever the configured cap has been reached

Each input bar is a final OHLC bar. With ``confirm_bar=True``, step 2 is the
bar-close (confirmed) evaluation of that same bar, matching the Pine script's
``barstate.isconfirmed`` gate: there is no one-bar look-back delay, and the
ATR is the value of the gap bar itself. With ``confirm_bar=False``, the mock
still uses final bar values (a historical-bar simplification); it does not
model intra-bar ticks or repainting.

Scope of verification: ``confirm_bar`` does not change the mock's arithmetic
— in a bar-level model both settings evaluate the same final bar values.
What the mock verifies is therefore the state transitions computed from
confirmed (final) OHLC bars. The tick-level behaviour of Pine's
``barstate.isconfirmed`` gate on a forming bar (including drawing rollback)
is NOT verified by the mock; it is a TradingView manual-check item.

The mock is used to verify the *logic* (not Pine syntax) on synthetic OHLC
series whose expected behavior is known by construction.

Run:  python3 gap_logic_mock.py     (exit code 0 = all tests passed)
"""

from dataclasses import dataclass, field


@dataclass
class GapBoxM:
    top: float
    bot: float
    mid: float
    birth: int          # index of the newer gap candle
    bull: bool          # True = gap up
    mid_hit: bool = False


def atr_series(bars, length):
    """Wilder ATR (the smoothing used by Pine's ta.atr).

    Returns a list with None before the first ATR value. The first value, at
    index ``length - 1``, is the simple average of the first ``length`` true
    ranges; later values use Wilder's recursive smoothing.
    """
    values = [None] * len(bars)
    true_ranges = []
    previous_atr = None
    for i, (_o, h, l, _c) in enumerate(bars):
        if i == 0:
            true_range = h - l
        else:
            prev_close = bars[i - 1][3]
            true_range = max(h - l, abs(h - prev_close), abs(l - prev_close))
        true_ranges.append(true_range)
        if i == length - 1:
            previous_atr = sum(true_ranges) / length
            values[i] = previous_atr
        elif i >= length:
            previous_atr = (previous_atr * (length - 1) + true_range) / length
            values[i] = previous_atr
    return values


def run(bars, span=2, min_pct=0.0, max_bars=100, max_boxes=50,
        confirm_bar=False, min_mode="Percent", min_val=None, atr_len=14):
    """Simulate the indicator over bars = [(o, h, l, c), ...].

    ``confirm_bar`` selects the bar-close detection model described in the
    module docstring; detection still refers to the gap bar itself. It does
    not alter the mock's results (bar-level model; see module docstring).
    ``min_mode`` is "Percent", "Price", or "ATR multiple". For Percent mode,
    ``min_val`` defaults to the legacy ``min_pct`` argument.

    Returns (events, final_boxes).
    events: list of (bar_index, kind, detail) with kind in
            {"create", "mid", "fill", "expire", "evict"}.
    """
    # Reject impossible candles up front: every bar must satisfy
    # low <= open <= high and low <= close <= high, as real OHLC data does.
    for o, h, l, c in bars:
        assert l <= o <= h, f"invalid OHLC bar: open {o} outside [{l}, {h}]"
        assert l <= c <= h, f"invalid OHLC bar: close {c} outside [{l}, {h}]"
    boxes = []
    events = []
    atr_values = atr_series(bars, atr_len)

    for i, (_o, h, l, _c) in enumerate(bars):
        # ---- 1) manage existing boxes (iterate newest -> oldest) --------
        survivors = []
        for g in reversed(boxes):
            age = i - g.birth
            filled = (l <= g.bot) if g.bull else (h >= g.top)
            # A first midline touch is recorded before deletion, so a bar
            # that both touches the midline and fills the gap emits both
            # events, in that order.
            if not g.mid_hit:
                touched = (l <= g.mid) if g.bull else (h >= g.mid)
                if touched:
                    g.mid_hit = True
                    events.append((i, "mid", g))
            if filled:
                events.append((i, "fill", g))
                continue
            if age >= max_bars:
                events.append((i, "expire", g))
                continue
            survivors.append(g)
        boxes = list(reversed(survivors))

        # ---- 2) detect a new gap ----------------------------------------
        # In confirm mode this step represents the confirmed close of bar i;
        # in live mode it is the historical-bar simplification documented at
        # the top of this file. Either way the newer candle is bar i itself.
        if i >= span:
            _o2, old_h, old_l, _c2 = bars[i - span]
            new_h, new_l = h, l
            gap_up = new_l > old_h
            gap_dn = new_h < old_l
            if gap_up or gap_dn:
                bull = gap_up
                top = new_l if bull else old_l
                bot = old_h if bull else new_h
                size = (new_l - old_h) if bull else (old_l - new_h)
                ref = old_h if bull else old_l
                if min_mode == "Percent":
                    pct = min_pct if min_val is None else min_val
                    threshold = abs(ref) * pct / 100.0
                elif min_mode == "Price":
                    threshold = 0.0 if min_val is None else min_val
                elif min_mode == "ATR multiple":
                    multiple = 0.0 if min_val is None else min_val
                    if multiple == 0.0:
                        threshold = 0.0
                    elif atr_values[i] is None:
                        threshold = None
                    else:
                        threshold = multiple * atr_values[i]
                else:
                    raise ValueError(f"unknown min_mode: {min_mode}")
                if threshold is not None and size >= threshold:
                    # Enforce the cap before creation: the number of live
                    # boxes never exceeds max_boxes, even temporarily.
                    while len(boxes) >= max_boxes:
                        evicted = boxes.pop(0)
                        events.append((i, "evict", evicted))
                    g = GapBoxM(top=top, bot=bot, mid=(top + bot) / 2.0,
                                birth=i, bull=bull)
                    boxes.append(g)
                    events.append((i, "create", g))
    return events, boxes


# ---------------------------------------------------------------------------
# Tests — every series is hand-built so the expected outcome is known.
# Bar format: (open, high, low, close)
# ---------------------------------------------------------------------------

def kinds(events, kind):
    return [e for e in events if e[1] == kind]


def test_bull_gap_mid_then_fill():
    # span=2: bar0 high=100 is the older candle; bar2 low=110 -> gap 100..110,
    # mid=105. bar3 dips to 104 (mid touch, no fill). bar4 dips to 99 (fill).
    bars = [
        (98, 100, 95, 99),      # 0 older candle
        (100, 104, 99, 103),    # 1 in-between
        (111, 115, 110, 112),   # 2 gap candle (low 110 > high[0] 100)
        (110, 113, 104, 108),   # 3 low 104 <= mid 105 -> mid touch
        (105, 112, 99, 101),    # 4 low 99 <= bot 100 -> filled
                                #    (high 112 >= low[2] 110, so bar4 itself
                                #     forms no opposite gap vs bar2)
    ]
    events, boxes = run(bars, span=2)
    assert len(kinds(events, "create")) == 1 and kinds(events, "create")[0][0] == 2
    g = kinds(events, "create")[0][2]
    assert (g.top, g.bot, g.mid, g.bull) == (110, 100, 105.0, True)
    assert [e[0] for e in kinds(events, "mid")] == [3]
    assert [e[0] for e in kinds(events, "fill")] == [4]
    assert boxes == []
    print("PASS test_bull_gap_mid_then_fill")


def test_bear_gap_fill_without_mid_event_order():
    # span=2 bearish gap: bar0 low=100 (older), bar2 high=90 -> zone 90..100,
    # mid=95. bar3 high=96 -> mid touch. bar4 high=101 -> filled (>= top 100).
    # bar1 and bar4 ranges are chosen so they form no gaps of their own
    # against bars 2 bars back (bar4's low 89 <= high[2] 90, etc.).
    bars = [
        (102, 105, 100, 103),   # 0 older candle
        (98, 102, 94, 96),      # 1 in-between
        (87, 90, 85, 88),       # 2 gap candle (high 90 < low[0] 100)
        (90, 96, 88, 94),       # 3 high 96 >= mid 95 -> mid touch
        (95, 101, 89, 100),     # 4 high 101 >= top 100 -> filled
    ]
    events, boxes = run(bars, span=2)
    assert len(kinds(events, "create")) == 1
    g = kinds(events, "create")[0][2]
    assert (g.top, g.bot, g.mid, g.bull) == (100, 90, 95.0, False)
    assert [e[0] for e in kinds(events, "mid")] == [3]
    assert [e[0] for e in kinds(events, "fill")] == [4]
    assert boxes == []
    print("PASS test_bear_gap_fill_without_mid_event_order")


def test_expiry_after_max_bars():
    # Bull gap at bar2, price never comes back; max_bars=3 -> the box is
    # deleted when its age reaches 3, i.e. on bar5.
    # Note: with the span=2 definition, bar3 also gaps up against bar1
    # (low 111 > high[1] 104), creating a second box that expires on bar6.
    # Both expiries are asserted; no fill ever happens.
    bars = [
        (98, 100, 95, 99),
        (100, 104, 99, 103),
        (111, 115, 110, 112),   # 2 gap A
        (112, 116, 111, 114),   # 3 gap B (vs bar1); A age 1
        (114, 117, 112, 115),   # 4 A age 2, B age 1
        (115, 118, 113, 116),   # 5 A age 3 -> expire; B age 2
        (116, 119, 114, 117),   # 6 B age 3 -> expire
    ]
    events, boxes = run(bars, span=2, max_bars=3)
    assert [e[0] for e in kinds(events, "create")] == [2, 3]
    assert [e[0] for e in kinds(events, "expire")] == [5, 6]
    assert kinds(events, "fill") == []
    assert boxes == []
    print("PASS test_expiry_after_max_bars")


def test_min_gap_percent_threshold():
    # Gap of 1.0 on a reference of 100 = 1%. With min_pct=2 -> no box.
    bars = [
        (98, 100, 95, 99),
        (100, 102, 99, 101),
        (103, 108, 101, 105),   # low 101 > high[0] 100 -> size 1.0 (1%)
    ]
    events, boxes = run(bars, span=2, min_pct=2.0)
    assert events == [] and boxes == []
    events, boxes = run(bars, span=2, min_pct=0.5)
    assert len(kinds(events, "create")) == 1
    print("PASS test_min_gap_percent_threshold")


def test_cap_evicts_oldest():
    # Three bull gaps (bars 2, 5, 8) with max_boxes=2 -> the first box is
    # evicted when the third is created; boxes B and C remain.
    # Every non-gap bar is checked by hand to form no gap against the bar
    # 2 back (e.g. bar3 low 108 <= high[1] 112; bar6 low 119 <= high[4] 120)
    # and no bar's low ever reaches an open zone's bottom (no fills).
    # Bar6 does cross gap B's midline (a harmless "mid" event here).
    bars = [
        (98, 100, 95, 99),      # 0
        (100, 112, 99, 110),    # 1
        (111, 115, 110, 112),   # 2 gap A: low 110 > high[0] 100 (zone 100..110)
        (112, 118, 108, 115),   # 3 no gap vs bar1 (low 108 <= 112)
        (115, 120, 113, 118),   # 4 no gap vs bar2 (low 113 <= 115)
        (128, 132, 125, 130),   # 5 gap B: low 125 > high[3] 118 (zone 118..125)
        (124, 127, 119, 122),   # 6 no gap vs bar4 (low 119 <= 120)
        (130, 134, 128, 131),   # 7 no gap vs bar5 (low 128 <= 132)
        (137, 142, 135, 140),   # 8 gap C: low 135 > high[6] 127 (zone 127..135)
    ]
    events, boxes = run(bars, span=2, max_boxes=2)
    creates = kinds(events, "create")
    evicts = kinds(events, "evict")
    assert [e[0] for e in creates] == [2, 5, 8], creates
    assert len(evicts) == 1 and evicts[0][0] == 8
    assert evicts[0][2].birth == 2          # oldest (gap A) evicted
    assert sorted(g.birth for g in boxes) == [5, 8]
    # The cap is enforced before creation: at bar 8 the eviction event must
    # precede the creation event (no temporary third live box).
    assert [e[1] for e in events if e[0] == 8] == ["evict", "create"]
    print("PASS test_cap_evicts_oldest")


def test_confirm_mode_filled_next_bar_does_not_linger():
    # Regression for the bar-close detection delay: the gap forms on bar2
    # (zone 100..110) and is detected at that bar's close; bar3 falls to 95
    # and fills it completely. The box must be gone afterwards — it must not
    # survive to expiry because registration was delayed by one bar.
    bars = [
        (98, 100, 95, 99),      # 0 older candle
        (100, 104, 99, 103),    # 1 in-between
        (111, 115, 110, 112),   # 2 gap candle (low 110 > high[0] 100)
        (105, 112, 95, 100),    # 3 low 95 <= bot 100 -> mid + fill
        (116, 125, 114, 120),   # 4 no gap vs bar2 (low 114 <= high[2] 115)
    ]
    events, boxes = run(bars, span=2, confirm_bar=True)
    assert [e[0] for e in kinds(events, "create")] == [2]
    assert [e[0] for e in kinds(events, "mid")] == [3]
    assert [e[0] for e in kinds(events, "fill")] == [3]
    assert boxes == []
    print("PASS test_confirm_mode_filled_next_bar_does_not_linger")


def test_mid_and_fill_on_same_bar_emit_both_events():
    # Bar3 trades straight through the midline (105) and the far edge (100)
    # of the bullish gap created on bar2. Both events must fire on bar3,
    # midline first, even though the box is deleted on that bar.
    bars = [
        (98, 100, 95, 99),      # 0 older candle
        (100, 104, 99, 103),    # 1 in-between
        (111, 115, 110, 112),   # 2 gap candle, zone 100..110, mid 105
        (105, 112, 99, 101),    # 3 low 99 <= mid and <= bot
    ]
    events, boxes = run(bars, span=2)
    assert [e[1] for e in events if e[0] == 3] == ["mid", "fill"]
    assert boxes == []
    print("PASS test_mid_and_fill_on_same_bar_emit_both_events")


def test_atr_threshold_uses_gap_bar_atr():
    # atr_len=1, so ATR is the current bar's true range. Bar0's ATR is 10;
    # bar1's true range is 7 (high 102 vs. previous close 95). The gap size
    # is 1.0, so with a 0.12 multiple the gap-bar threshold is 0.84 (pass),
    # while the previous bar's ATR would give 1.2 (fail). Creation therefore
    # proves the threshold uses the gap bar's own ATR.
    bars = [
        (95, 100, 90, 95),      # 0 TR = 10
        (101, 102, 101, 101.5), # 1 low 101 > high[0] 100, TR = 7
    ]
    events, boxes = run(bars, span=1, min_mode="ATR multiple",
                        min_val=0.12, atr_len=1)
    assert len(kinds(events, "create")) == 1
    assert len(boxes) == 1
    print("PASS test_atr_threshold_uses_gap_bar_atr")


def test_atr_zero_threshold_qualifies_before_atr_ready():
    # With an ATR multiple of 0 the threshold is exactly 0.0, so a gap
    # qualifies even while the ATR itself is still na (atr_len=14 but only
    # two bars of history).
    bars = [
        (95, 100, 90, 95),      # 0
        (106, 109, 105, 107),   # 1 low 105 > high[0] 100
    ]
    events, boxes = run(bars, span=1, min_mode="ATR multiple",
                        min_val=0.0, atr_len=14)
    assert len(kinds(events, "create")) == 1
    assert len(boxes) == 1
    print("PASS test_atr_zero_threshold_qualifies_before_atr_ready")


def test_atr_positive_threshold_waits_for_atr():
    # Same series with a positive multiple: while the ATR is na there is no
    # numeric threshold, so nothing may qualify yet.
    bars = [
        (95, 100, 90, 95),      # 0
        (106, 109, 105, 107),   # 1 low 105 > high[0] 100
    ]
    events, boxes = run(bars, span=1, min_mode="ATR multiple",
                        min_val=0.5, atr_len=14)
    assert events == [] and boxes == []
    print("PASS test_atr_positive_threshold_waits_for_atr")


def test_consecutive_mode():
    # span=1: gap between bar1 (high 100) and bar2 (low 105).
    bars = [
        (95, 99, 93, 97),       # 0
        (97, 100, 96, 99),      # 1
        (106, 109, 105, 107),   # 2 low 105 > high[1] 100 -> gap 100..105
        (106, 108, 103, 104),   # 3 low 103 > bot 100, <= mid 102.5? no: 103 > 102.5 -> nothing
        (104, 106, 101, 102),   # 4 low 101 <= mid 102.5 -> mid touch
    ]
    events, boxes = run(bars, span=1)
    assert len(kinds(events, "create")) == 1
    g = kinds(events, "create")[0][2]
    assert (g.top, g.bot, g.mid) == (105, 100, 102.5)
    assert [e[0] for e in kinds(events, "mid")] == [4]
    assert len(boxes) == 1
    print("PASS test_consecutive_mode")


def test_no_gap_no_box():
    bars = [(100 + i, 102 + i, 99 + i, 101 + i) for i in range(10)]
    events, boxes = run(bars, span=2)
    assert events == [] and boxes == []
    print("PASS test_no_gap_no_box")


if __name__ == "__main__":
    test_bull_gap_mid_then_fill()
    test_bear_gap_fill_without_mid_event_order()
    test_expiry_after_max_bars()
    test_min_gap_percent_threshold()
    test_cap_evicts_oldest()
    test_confirm_mode_filled_next_bar_does_not_linger()
    test_mid_and_fill_on_same_bar_emit_both_events()
    test_atr_threshold_uses_gap_bar_atr()
    test_atr_zero_threshold_qualifies_before_atr_ready()
    test_atr_positive_threshold_waits_for_atr()
    test_consecutive_mode()
    test_no_gap_no_box()
    print("ALL TESTS PASSED")
