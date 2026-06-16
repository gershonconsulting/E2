#!/usr/bin/env python3
"""florida_pipeline.py -- Download -> parse -> score -> ranked CSVs
Usage:
  python3 florida_pipeline.py                        # download today
    python3 florida_pipeline.py --date 20260612        # specific date
      python3 florida_pipeline.py --file 20260612c.txt   # use local file
        python3 florida_pipeline.py --inspect 20260612c.txt # verify offsets
        """
import argparse, csv, sys
from datetime import datetime
from pathlib import Path
import paramiko
from field_spec import parse_record
from scoring import score_record

SFTP_HOST = "sftp.floridados.gov"
SFTP_PORT = 22
SFTP_USER = "Public"
SFTP_PASS = "PubAccess1845!"
SFTP_PATH = "doc/cor/{date}c.txt"
OUT_DIR = Path("out")


def download(date_str):
      OUT_DIR.mkdir(exist_ok=True)
      remote = SFTP_PATH.format(date=date_str)
      local = OUT_DIR / f"{date_str}c.txt"
      print(f"[pipeline] SFTP {SFTP_HOST} -> {remote}")
      t = paramiko.Transport((SFTP_HOST, SFTP_PORT))
      t.connect(username=SFTP_USER, password=SFTP_PASS)
      s = paramiko.SFTPClient.from_transport(t)
      s.get(remote, str(local))
      s.close(); t.close()
      print(f"[pipeline] Saved {local}")
      return local


def inspect(path):
      with open(path, "rb") as f:
                line = f.readline()
            print(f"Record length: {len(line)} bytes")
    rec = parse_record(line)
    for k, v in rec.items():
              if k != "officers":
                            print(f"  {k:25s}: {repr(v)}")
                    for i, o in enumerate(rec.get("officers", [])):
                              print(f"  officer[{i}]: {o}")


def process(path, date_str):
      OUT_DIR.mkdir(exist_ok=True)
    tier_order = {"Qualified": 0, "Review": 1, "Filler": 2}
    all_rows, prospects = [], []
    with open(path, "rb") as f:
              for raw in f:
                            line = raw.rstrip(b"\r\n")
                            if not line: continue
                                          try:
                                                            rec = parse_record(line)
except Exception as e:
                print(f"[pipeline] parse error: {e}", file=sys.stderr); continue
            s = score_record(rec)
            if s["tier"] == "Excluded": continue
                          row = {
                                            "tier":              s["tier"],
                                            "corp_name":         rec.get("corp_name", ""),
                                            "document_number":   rec.get("document_number", ""),
                                            "date_filed":        rec.get("date_filed", ""),
                                            "principal_city":    rec.get("principal_city", ""),
                                            "principal_state":   rec.get("principal_state", ""),
                                            "principal_country": rec.get("principal_country", ""),
                                            "officers":          "; ".join(
                                                                  f"{o.get('officer_name','')} ({o.get('officer_country','')})"
                                                                  for o in rec.get("officers", [])),
                                            "treaty_country":    s["treaty_country"],
                                            "reason":            s["reason"],
                          }
            all_rows.append(row)
            if s["tier"] in ("Qualified", "Review"):
                              prospects.append(row)
                  for lst in (all_rows, prospects):
                            lst.sort(key=lambda r: tier_order.get(r["tier"], 9))
    fields = ["tier","corp_name","document_number","date_filed",
                            "principal_city","principal_state","principal_country",
                            "officers","treaty_country","reason"]
    def write_csv(rows, p):
              with open(p, "w", newline="", encoding="utf-8") as f:
                            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    write_csv(all_rows,  OUT_DIR / f"e2_florida_all_{date_str}.csv")
    write_csv(prospects, OUT_DIR / f"e2_florida_prospects_{date_str}.csv")
    print(f"[pipeline] {len(all_rows)} rows, {len(prospects)} prospects -> out/")
    return all_rows, prospects


def main():
      ap = argparse.ArgumentParser(description="Florida E-2 pipeline")
    ap.add_argument("--date"); ap.add_argument("--file"); ap.add_argument("--inspect")
    args = ap.parse_args()
    if args.inspect:
              inspect(args.inspect); return
    if args.file:
              p = Path(args.file); ds = args.date or p.stem[:8]; process(p, ds)
else:
        ds = args.date or datetime.now().strftime("%Y%m%d")
        process(download(ds), ds)

if __name__ == "__main__":
      main()
