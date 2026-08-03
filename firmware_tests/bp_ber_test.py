import time
import logging
import numpy as np
import matplotlib.pyplot as plt
import pytest
from pathlib import Path
from matplotlib.colors import LogNorm  # <-- NEW
from wtl.pytest_xreport import xr, get_xr_from
from pychfpga.fpga_array import FPGAArray

pytestmark = pytest.mark.backplane_links  # groups these in the HTML report

TX_TO_RX_LANE_MAP = {
    (1, 0): (1, 0), (1, 1): (4, 3), (1, 2): (3, 3), (1, 3): (2, 3),
    (2, 0): (2, 0), (2, 1): (1, 3), (2, 2): (3, 2), (2, 3): (4, 2),
    (3, 0): (3, 0), (3, 1): (4, 1), (3, 2): (2, 2), (3, 3): (1, 2),
    (4, 0): (4, 0), (4, 1): (3, 1), (4, 2): (2, 1), (4, 3): (1, 1),
}
RX_TO_TX_LANE_MAP = {rx: tx for tx, rx in TX_TO_RX_LANE_MAP.items()}


class TestBackplaneBER:
    """
    Minimal sweep with compact summary:
      - PyTest parametrizes (power, pre, post): one run per configuration -- this test is geared towards doing sweeps across power settings
      - After last run: for each POWER, plot a heatmap:
          X = postcursor, Y = precursor, Color = worst-lane BER (log)
          green dots mark (pre, post) where ALL links had ZERO errors
    """

    # tiny aggregator
    _agg_by_power = {}   # {power: [{"pre": int, "post": int, "worst_ber": float, "zero_all": bool}]}
    _remaining = None    # total number of parametrized cases


    #parameters for per link study
    _slots = None                  
    _pair_agg = {}                   
    _pair_lane_counts = {}          



    def pytest_generate_tests(self, metafunc):
        xr = get_xr_from(metafunc)
        print(xr)
        tc = xr.config.test_config
        bp = tc.get("bp_params", {})

        def param(name, default=None):
            if name in bp:
                metafunc.parametrize(name, bp[name])
            elif default is not None and name in metafunc.fixturenames:
                metafunc.parametrize(name, [default])

        # Parametrize so pytest does full Cartesian product
        param("prbs_type", default=5)
        param("tx_power", default=0)
        param("tx_precursor", default=2)
        param("tx_postcursor", default=0)
        param("dwell_time", default=1.0)
        param("bit_rate", default=25e9)
        param("max_allowed_ber", default=1e-12)

        # Count total test cases so we know when to render final heatmaps
        def _len_for(name):
            v = bp.get(name, None)
            if v is None:
                return 1
            try:
                return len(v)
            except TypeError:
                return 1

        names = ["prbs_type", "tx_power", "tx_precursor", "tx_postcursor",
                 "dwell_time", "bit_rate", "max_allowed_ber"]
        total = 1
        for n in names:
            total *= _len_for(n)

        metafunc.module.TestBackplaneBER._remaining = total
        metafunc.module.TestBackplaneBER._agg_by_power = {}
        metafunc.module.TestBackplaneBER._pair_agg = {}          
        metafunc.module.TestBackplaneBER._pair_lane_counts = {} 


        # Helpful collector print so you can verify sweep breadth
        def _val(v, dflt):
            return list(v) if isinstance(v, (list, tuple, range)) else ([v] if v is not None else [dflt])
        print("Collected configurations:",
              "power=", _val(bp.get("tx_power"), 0),
              "pre=",   _val(bp.get("tx_precursor"), 2),
              "post=",  _val(bp.get("tx_postcursor"), 0),
              "| total cases =", total)



    def ca_conn(self, xr):
        if "ca" in xr.data:
            return xr.data.ca
        ca = FPGAArray(**self.connection_config)
        xr.data.ca = ca
        xr.data.boards_by_slot = {ib.slot: ib for ib in ca.ib}
        xr.data.board = xr.data.boards_by_slot[min(xr.data.boards_by_slot)]
        return ca

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, xr):
        self.xr = xr
        self.test_config = xr.config.test_config
        self.connection_config = xr.config.connection_config

        self.ca = self.ca_conn(xr)
        self.boards_by_slot = xr.data.boards_by_slot
        self.board = xr.data.board

        self.SAMPLES_PER_FRAME = self.board.ADC_SAMPLES_PER_FRAME
        self.ADC_BITS_PER_SAMPLE = self.board.ADC_BITS_PER_SAMPLE
        self.PLATFORM = self.board.mb.part_number

        type(self)._slots = sorted(self.boards_by_slot.keys()) 

        # Build expected lane-counts per TX->RX slot pair (from static map)  
        lane_counts = {}
        for (tx_slot, _tx_lane), (rx_slot, _rx_lane) in TX_TO_RX_LANE_MAP.items():
            lane_counts[(tx_slot, rx_slot)] = lane_counts.get((tx_slot, rx_slot), 0) + 1
        type(self)._pair_lane_counts = lane_counts

        #mark which gty links are present
        present = set(self.boards_by_slot.keys())
        self.active_tx_to_rx = {
            tx: rx for tx, rx in TX_TO_RX_LANE_MAP.items()
            if tx[0] in present and rx[0] in present
        }
        self.active_rx_to_tx = {rx: tx for tx, rx in self.active_tx_to_rx.items()}



        conn_logger_name = FPGAArray.__name__.rsplit(".", 1)[0] if "." in __name__ else ""
        self.logger = logging.getLogger(conn_logger_name)
        self.logger.setLevel(self.test_config.get("logleveltest", "DEBUG"))

        self.plot_dir = Path("plots/")

    # hardware helpers
    def _reset_links(self):
        for ib in self.ca.ib:
            ib.GPIO.ANT_RESET = 0
            ib.GPIO.CORR_RESET = 1
            ib.GPIO.CORR_RESET = 0
        for ib in self.ca.ib:
            b = ib.CT.BPLINKS
            assert not (b.CORE_RESET or b.TX_RESET or b.RX_PLL_DATAPATH_RESET or b.RX_DATAPATH_RESET or b.RX_RESET)
        for ib in self.ca.ib:
            ib.GPIO.ANT_RESET = 1
            ib.GPIO.CORR_RESET = 1
            ib.GPIO.CORR_RESET = 0
            ib.GPIO.ANT_RESET = 0

    def _configure_prbs(self, prbs, pwr, pre, post):
        tx_enabled_slots = {tx_slot for (tx_slot, _), _ in self.active_tx_to_rx.items()}
        for ib in self.ca.ib:
            for g in ib.CT.BPLINKS.gty:
                g.TXPRBSSEL = g.RXPRBSSEL = prbs
                g.TXDIFFCTRL = pwr
                g.TXPRECURSOR = pre
                g.TXPOSTCURSOR = post
                g.TXPRBSFORCEERR = 0
                g.RXLPMEN = 0
                g.TXINHIBIT = 0 if ib.slot in tx_enabled_slots else 1
                g.LOOPBACK = 0

    def _retrain_and_clear(self):
        for ib in self.ca.ib:
            for g in ib.CT.BPLINKS.gty:
                g.reset_rx_equalizer()
        time.sleep(0.001)
        for ib in self.ca.ib:
            for g in ib.CT.BPLINKS.gty:
                g.RXPRBSCNTRESET = 1
                g.RXPRBSCNTRESET = 0


    # -------- the test (one run per configuration) --------
    def test_backplane_ber(
        self, xr, prbs_type, tx_power, tx_precursor, tx_postcursor, dwell_time, bit_rate, max_allowed_ber
    ):
        log = self.logger
        log.info(
            "PRBS BER: PRBS=%s, PWR=%s, PRE=%s, POST=%s, dwell=%.2fs, bit_rate=%.3e",
            prbs_type, tx_power, tx_precursor, tx_postcursor, dwell_time, bit_rate,
        )

        self._reset_links()
        self._configure_prbs(prbs_type, tx_power, tx_precursor, tx_postcursor)
        time.sleep(0.3)          # TX settle
        self._retrain_and_clear()
        time.sleep(dwell_time)   # accumulate

        labels, bers, errs = [], [], []
        pair_bucket = {} 
        for ib in self.ca.ib:
            for g in ib.CT.BPLINKS.gty:
                rx = (ib.slot, g.instance_number + 1)
                tx = RX_TO_TX_LANE_MAP.get(rx)

                if tx is None:
                    continue 

                err = int(g.ERR_CTR)
                ber_floor = 1.0 / (bit_rate * dwell_time)

                if err == 0:
                    ber = ber_floor          # <- store the floor as the value you plot/aggregate
                    log.info("Tx%s->Rx%s: err=0  BER<=%.1e (using floor for plots)", tx, rx, ber_floor)
                else:
                    ber = err / (bit_rate * dwell_time)
                    log.info("Tx%s->Rx%s: err=%d  BER %.1e", tx, rx, err, ber)

                # collect per TX-slot -> RX-slot
                labels.append(f"Tx{tx}->Rx{rx}")
                bers.append(ber)
                errs.append(err)

                tx_slot, _ = tx
                rx_slot, _ = rx
                pair_bucket.setdefault((tx_slot, rx_slot), []).append({
                    "pre": int(tx_precursor),
                    "post": int(tx_postcursor),
                    "ber": float(ber),
                    "err": int(err),
                })



        # Record for heatmap summary
        worst_ber = max(bers) if bers else float("inf")
        zero_all = all(e == 0 for e in errs)
        cls = type(self)
        cls._agg_by_power.setdefault(int(tx_power), []).append({
            "pre": int(tx_precursor),
            "post": int(tx_postcursor),
            "worst_ber": float(worst_ber),
            "zero_all": bool(zero_all),
        })

        # Persist per-pair bucket (across all runs)  
        pwr = int(tx_power)
        per_pwr_map = cls._pair_agg.setdefault(pwr, {})
        for k, items in pair_bucket.items():
            per_pwr_map.setdefault(k, []).extend(items)



        # If only_plot, ignore pytest fails
        if not self.test_config.get("only_plot", False):
            fail_msgs = []
            for lbl, e, b in zip(labels, errs, bers):
                if e and b > max_allowed_ber:
                    fail_msgs.append(f"{lbl}: BER {b:.3e} > {max_allowed_ber:.3e} (err={e}, dwell={dwell_time}s)")
            if fail_msgs:
                pytest.fail("\n".join(fail_msgs))

        # Final heatmaps when last parametrized test finishes
        cls._remaining -= 1
        if cls._remaining == 0:
            print("\n===== Backplane BER sweep summary (heatmaps per power) =====")
            for pwr in sorted(cls._agg_by_power):
                entries = cls._agg_by_power[pwr]

                # unique sorted pre/post axes
                pre_vals = sorted({e["pre"] for e in entries})
                post_vals = sorted({e["post"] for e in entries})
                pi = {v: i for i, v in enumerate(pre_vals)}
                pj = {v: j for j, v in enumerate(post_vals)}

                # heatmap of worst-lane BER
                heat = np.full((len(pre_vals), len(post_vals)), np.nan)
                for e in entries:
                    i, j = pi[e["pre"]], pj[e["post"]]
                    v = e["worst_ber"]
                    # If multiple measurements hit the same cell, keep the BEST (lowest) BER
                    if np.isnan(heat[i, j]):
                        heat[i, j] = v
                    else:
                        heat[i, j] = min(heat[i, j], v)


                # protect in case of negative values
                Z = heat.copy()
                Z[(Z <= 0) & np.isfinite(Z)] = 1e-16

                def _edges_from_vals(vals):
                    vals = np.asarray(vals, dtype=float)
                    if len(vals) == 1:
                        # single value → make a 1-wide box around it
                        return np.array([vals[0]-0.5, vals[0]+0.5])
                    mids = (vals[:-1] + vals[1:]) / 2.0
                    first = vals[0] - (mids[0] - vals[0])
                    last  = vals[-1] + (vals[-1] - mids[-1])
                    return np.concatenate(([first], mids, [last]))

                x_edges = _edges_from_vals(post_vals)
                y_edges = _edges_from_vals(pre_vals)



                fig, ax = plt.subplots()
                pcm = ax.pcolormesh(
                    x_edges, y_edges, Z,
                    norm=LogNorm(vmin=np.nanmin(Z[np.isfinite(Z)]), vmax=np.nanmax(Z[np.isfinite(Z)])),
                    shading="flat"
                )
                cbar = fig.colorbar(pcm, ax=ax)
                cbar.set_label("Worst-lane BER (log)")

                # green dots exactly at (post, pre) where ALL links had zero errs
                zero_pts = [(e["post"], e["pre"]) for e in entries if e["zero_all"]]
                if zero_pts:
                    xs, ys = zip(*zero_pts)
                    ax.scatter(xs, ys, s=60)  # optional: add color='g' if you want explicitly green

                ax.set_xlabel("TX postcursor")
                ax.set_ylabel("TX precursor")
                ax.set_title(f"Worst-lane BER heatmap — PWR={pwr} — DwellTime={dwell_time}")
                ax.set_xticks(post_vals)
                ax.set_yticks(pre_vals)
                ax.set_xlim(x_edges[0], x_edges[-1])
                ax.set_ylim(y_edges[0], y_edges[-1])
                plt.tight_layout()
                xr.insert_plot()
                plt.close(fig)



                #plot the per link map
                all_vals = []
                pair_map = cls._pair_agg.get(pwr, {})
                for pair_key, items in pair_map.items():
                    # worst BER per (pre, post) for the pair
                    grid = {}
                    for it in items:
                        key = (it["pre"], it["post"])
                        v = it["ber"]
                        grid[key] = max(grid.get(key, 0.0), v)
                    for v in grid.values():
                        all_vals.append(v)

                if not all_vals:
                    print(f"(PWR={pwr}) No per-pair data; skipping link matrix.")
                    continue

                vmin = np.nanmin(all_vals)
                vmax = np.nanmax(all_vals)
                if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin <= 0:
                    vmin = 1e-16
                    vmax = max(vmax, 1e-12)

                slots = cls._slots or sorted({s for (s, _) in cls._pair_lane_counts})
                n = len(slots)
                fig, axes = plt.subplots(n, n, figsize=(2.4*n, 2.4*n), squeeze=False, constrained_layout=True)
                fig.suptitle(f"Per-link BER heatmaps (TX→RX) — PWR={pwr}")

                # quick indexers
                pi = {v: i for i, v in enumerate(pre_vals)}
                pj = {v: j for j, v in enumerate(post_vals)}

                last_pcm = None
                for r, tx_slot in enumerate(slots):
                    for c, rx_slot in enumerate(slots):
                        ax = axes[r][c]

                        #map all tx -> rx
                        pair_key = (tx_slot, rx_slot)
                        items = pair_map.get(pair_key, None)
                        if not items:
                            ax.axis("off")
                            continue
                        # lower triangle only (i > j); hide diagonal and upper half

                        #if r <= c:
                        #    ax.axis("off")
                        #    continue

                        # build heat for this pair: worst BER per (pre, post)  # <<< NEW
                        heat = np.full((len(pre_vals), len(post_vals)), np.nan)
                        per_cfg_errs = {}
                        for it in items:
                            i, j = pi[it["pre"]], pj[it["post"]]
                            v = it["ber"]
                            heat[i, j] = max(heat[i, j], v) if np.isfinite(heat[i, j]) else v
                            per_cfg_errs.setdefault((it["pre"], it["post"]), []).append(it["err"])

                        Z = heat.copy()
                        Z[(Z <= 0) & np.isfinite(Z)] = 1e-16

                        pcm = ax.pcolormesh(
                            x_edges, y_edges, Z,
                            norm=LogNorm(vmin=vmin, vmax=vmax),
                            shading="flat"
                        )
                        last_pcm = pcm

                        # green dots where *all lanes of the pair* had zero errs at that (pre, post)  # <<< NEW
                        lane_target = cls._pair_lane_counts.get(pair_key, None)
                        zero_pts = []
                        if lane_target:
                            for (pre_v, post_v), errs_list in per_cfg_errs.items():
                                if len(errs_list) >= lane_target and all(e == 0 for e in errs_list):
                                    zero_pts.append((post_v, pre_v))
                        if zero_pts:
                            xs, ys = zip(*zero_pts)
                            ax.scatter(xs, ys, s=20)

                        # sparse ticks to keep readable
                        ax.set_title(f"{tx_slot}→{rx_slot}", fontsize=9)
                        ax.set_xlim(x_edges[0], x_edges[-1])
                        ax.set_ylim(y_edges[0], y_edges[-1])
                        if c == 0:
                            ax.set_yticks(pre_vals)
                            ax.set_ylabel("PRE")
                        else:
                            ax.set_yticklabels([])
                        if r == n - 1:
                            ax.set_xticks(post_vals)
                            ax.set_xlabel("POST")
                        else:
                            ax.set_xticklabels([])

                if last_pcm is not None:
                    cbar = fig.colorbar(last_pcm, ax=axes, fraction=0.02, pad=0.05)
                    cbar.set_label("Worst-lane BER (log)")

                xr.insert_plot()
                plt.close(fig)

                # summarize results
                tried = sorted({(e["pre"], e["post"]) for e in entries})
                zero_all_pairs = sorted({(e["pre"], e["post"]) for e in entries if e["zero_all"]})
                print(f"Power {pwr}: tried {len(tried)} combos -> {tried}")
                if zero_all_pairs:
                    print(f"Power {pwr}: ZERO errors on EVERY link at (pre, post): {zero_all_pairs}")
                else:
                    print(f"Power {pwr}: no (pre, post) achieved ZERO errors on EVERY link")