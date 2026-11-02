#!/usr/bin/env python3
"""Pengumpul snapshot order book Indodax (API publik, TANPA API key). Dijalankan terjadwal (GitHub Actions). Tiap panggilan: ambil ticker_all, pilih pasangan IDR dengan nilai transaksi 24 jam terbesar (+ BTC & ETH), ambil order book tiap pasangan, simpan ke JSONL. Hanya memakai pustaka standar Python. Batas API: 180 request/menit; di sini <= 2 request/detik."""
import json, os, sys, time, datetime as dt, urllib.request

BASE = "https://indodax.com"
TOP_N = int(os.environ.get("TOP_N", "20"))
LEVELS = int(os.environ.get("LEVELS", "25"))
PAUSE = float(os.environ.get("PAUSE", "0.5"))
CORE = ["btc_idr", "eth_idr"]
OUT_DIR = os.environ.get("OUT_DIR", "data/snapshots")


def get(path, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": "uas-trading-dryrun/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # retry terbatas
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"gagal {path}: {last}")


def parse_side(levels, reverse):
    out = []
    for x in levels[:LEVELS * 3]:
        try:
            out.append([float(x[0]), float(x[1])])
        except Exception:
            continue
    out.sort(key=lambda z: z[0], reverse=reverse)      # bid: harga tinggi dulu, ask: harga rendah dulu
    return out[:LEVELS]


def main():
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(OUT_DIR, exist_ok=True)
    errors = []
    st = get("/api/server_time")
    tick = get("/api/ticker_all")["tickers"]
    idr = [(k, float(v.get("vol_idr") or 0)) for k, v in tick.items() if k.endswith("_idr")]
    idr.sort(key=lambda x: -x[1])
    rank = {k: i + 1 for i, (k, _) in enumerate(idr)}
    vol = dict(idr)
    pairs = [k for k, _ in idr[:TOP_N]]
    for c in CORE:
        if c in tick and c not in pairs:
            pairs.append(c)
    lines = []
    for p in pairs:
        time.sleep(PAUSE)
        try:
            d = get("/api/depth/" + p.replace("_", ""))
            bids, asks = parse_side(d.get("buy", []), True), parse_side(d.get("sell", []), False)
            row = dict(ts_utc=now.isoformat(), server_time_ms=st.get("server_time"), pair=p, vol_idr_24h=vol.get(p),
                       rank_vol=rank.get(p), bids=bids, asks=asks)
            if bids and asks:
                row["best_bid"], row["best_ask"] = bids[0][0], asks[0][0]
                row["spread_pct"] = (asks[0][0] - bids[0][0]) / asks[0][0] * 100
            else:
                row["empty_book"] = True
            lines.append(row)
        except Exception as e:
            errors.append(dict(ts_utc=now.isoformat(), pair=p, error=str(e)))
    day = now.strftime("%Y-%m-%d")
    with open(os.path.join(OUT_DIR, day + ".jsonl"), "a", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    if errors:
        with open(os.path.join(OUT_DIR, "errors.log"), "a", encoding="utf-8") as f:
            for e in errors:
                f.write(json.dumps(e) + "\n")
    print(f"{now.isoformat()} snapshot {len(lines)} pasangan, {len(errors)} error")
    if not lines:
        sys.exit(1)


if __name__ == "__main__":
    main()
