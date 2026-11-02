#!/usr/bin/env python3
"""E2 / L-1 visa-signal collector for Gershon Consulting (task #08).

E-2 visa records are confidential by law (INA 222(f)) and USCIS stopped publishing
L-1 petitions by employer after FY2017, so no public list of E-2 / L-1 companies
exists. Both visas, however, require a foreign company to first SET UP a US
business. This script finds those set-ups in public filings, every day:

  1. SEC Form D  - a company headquartered abroad files Form D for a new US entity
                   (usually a Delaware corp) raising money from US investors.
                   Gives company, HQ city/country, industry, size band, amount and
                   the names of the executive officers (CEO).
  2. Florida     - daily Sunbiz filings whose principal address or home jurisdiction is
                   an E-2 treaty country (Florida is a top E-2 destination).
  3. Colorado    - a company formed abroad registers to do business in Colorado
                   (open data, updated daily).

Output: JSON list of candidates (one per company) on stdout or --out file.
Nothing here needs a key. SEC asks for a descriptive User-Agent with an email.

Usage: python3 signals.py --days 3 --out candidates.json
"""
import argparse, datetime as dt, json, re, sys, time, urllib.request

UA = "Gershon Consulting E2 research olivier@gershonconsulting.com"

# E-2 treaty countries (State Dept list), minus the countries Olivier excluded.
TREATY = {
 "ALBANIA","ARGENTINA","ARMENIA","AUSTRALIA","AUSTRIA","AZERBAIJAN","BAHRAIN","BANGLADESH",
 "BELGIUM","BOSNIA AND HERZEGOVINA","BULGARIA","CAMEROON","CANADA","CHILE","COLOMBIA",
 "COSTA RICA","CROATIA","CZECH REPUBLIC","CZECHIA","DENMARK","ECUADOR","EGYPT","ESTONIA",
 "ETHIOPIA","FINLAND","FRANCE","GEORGIA","GERMANY","GRENADA","HONDURAS","IRELAND","ISRAEL",
 "ITALY","JAMAICA","JAPAN","JORDAN","KAZAKHSTAN","KOREA, REPUBLIC OF","SOUTH KOREA","KOSOVO",
 "KYRGYZSTAN","LATVIA","LIBERIA","LITHUANIA","LUXEMBOURG","MACEDONIA","NORTH MACEDONIA",
 "MEXICO","MOLDOVA","MOLDOVA, REPUBLIC OF","MONGOLIA","MONTENEGRO","MOROCCO","NETHERLANDS",
 "NEW ZEALAND","NORWAY","OMAN","PAKISTAN","PANAMA","PARAGUAY","PHILIPPINES","POLAND",
 "PORTUGAL","ROMANIA","SENEGAL","SERBIA","SINGAPORE","SLOVAKIA","SLOVAK REPUBLIC","SLOVENIA",
 "SPAIN","SRI LANKA","SURINAME","SWEDEN","SWITZERLAND","TAIWAN","TAIWAN, PROVINCE OF CHINA",
 "THAILAND","TOGO","TRINIDAD AND TOBAGO","TUNISIA","TURKEY","TURKIYE","UKRAINE",
 "UNITED KINGDOM",
}
FUND_INDUSTRIES = {"Pooled Investment Fund","Other Banking and Financial Services","Investing",
                   "REITS and Finance","Insurance","Commercial Banking","Other Real Estate",
                   "Residential","Commercial","Construction"}
RESOURCE = re.compile(r"\b(gold|silver|copper|metals?|minerals?|mining|resources?|exploration|uranium|"
                      r"lithium|nickel|tungsten|bullion|royalt(y|ies)|petroleum|oil|gas|energy corp)\b", re.I)
RESOURCE_INDUSTRIES = {"Oil and Gas","Coal Mining","Other Energy","Energy Conservation","Electric Utilities"}
EXCLUDED = {"CN","IN","RU","BR","VN","ZA","SA","AE","HK","CHINA","INDIA","RUSSIA","BRAZIL","VIET NAM",
            "SOUTH AFRICA","SAUDI ARABIA","UNITED ARAB EMIRATES","HONG KONG"}
FUND_NAME = re.compile(r"\b(fund|L\.?P\.?|SPV|feeder|offshore|capital partners|holdings? LP|"
                       r"opportunit(y|ies)|SICAV|SCSp|VCC|trust|series of|a series)\b", re.I)
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
                "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR "
                "GU VI AS MP".split())
CANADA_PROV = {"A0","A1","A2","A3","A4","A5","A6","A7","A8","A9","B0","Z4"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            if attempt == 2:
                raise
            time.sleep(2 + attempt * 3)


def edgar_codes():
    t = get("https://www.sec.gov/submit-filings/filer-support-resources/edgar-state-country-codes")
    rows = re.findall(r"<tr[^>]*>\s*<td[^>]*>\s*([A-Z0-9]{2})\s*</td>\s*<td[^>]*>(.*?)</td>", t, re.S)
    import html
    return {c: html.unescape(re.sub("<.*?>", "", n)).strip().upper() for c, n in rows}


def business_days(n):
    d, out = dt.date.today(), []
    while len(out) < n:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def tag(x, t):
    m = re.search(rf"<{t}>(.*?)</{t}>", x, re.S)
    return m.group(1).strip() if m else ""


def form_d(days, codes, log):
    out = []
    for day in business_days(days):
        q = (day.month - 1) // 3 + 1
        url = f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{q}/form.{day:%Y%m%d}.idx"
        try:
            idx = get(url)
        except Exception as e:  # holiday / not yet published
            log(f"form D {day}: no index ({e.__class__.__name__})")
            continue
        rows = [l for l in idx.splitlines() if re.match(r"^D\s{2,}", l)]
        log(f"form D {day}: {len(rows)} new filings")
        for l in rows:
            path = l.split()[-1]
            cik, acc = path.split("/")[2], path.split("/")[-1].replace(".txt", "").replace("-", "")
            try:
                x = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml", 30)
            except Exception:
                continue
            finally:
                time.sleep(0.12)  # SEC fair-access: < 10 requests / second
            iss = re.search(r"<primaryIssuer>(.*?)</primaryIssuer>", x, re.S)
            iss = iss.group(1) if iss else x
            cc = tag(iss, "stateOrCountry")
            if not cc or cc in US_STATES:
                continue
            country = "CANADA" if cc in CANADA_PROV else codes.get(cc, cc)
            industry = tag(x, "industryGroupType")
            name = tag(iss, "entityName")
            if country not in TREATY or industry in FUND_INDUSTRIES or FUND_NAME.search(name):
                continue
            # Canadian listed junior miners raise from US accredited investors every week:
            # they are not entering the US market, so drop them.
            if industry in RESOURCE_INDUSTRIES or RESOURCE.search(name):
                continue
            people = []
            for rp in re.findall(r"<relatedPersonInfo>(.*?)</relatedPersonInfo>", x, re.S):
                fn, ln = tag(rp, "firstName"), tag(rp, "lastName")
                rel = re.findall(r"<relationship>(.*?)</relationship>", rp)
                people.append({"name": f"{fn} {ln}".strip(), "roles": rel,
                               "clarification": tag(rp, "relationshipClarification")})
            out.append({
                "source": "SEC Form D",
                "signal_date": str(day),
                "company": name,
                "hq_city": tag(iss, "city").title(),
                "hq_country": country.title(),
                "us_entity_state": tag(iss, "jurisdictionOfInc"),
                "year_of_inc": tag(tag(iss, "yearOfInc"), "value") or ("within 5 years" if "<withinFiveYears>true" in iss else ""),
                "industry": industry,
                "revenue_range": tag(x, "revenueRange"),
                "offering_usd": tag(x, "totalOfferingAmount"),
                "sold_usd": tag(x, "totalAmountSold"),
                "first_sale": tag(tag(x, "dateOfFirstSale"), "value"),
                "phone": tag(iss, "issuerPhoneNumber"),
                "people": people,
                "filing_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/",
                "signal": "Filed SEC Form D for its US entity (raising from US investors)",
            })
    return out


def colorado(days, log):
    since = (dt.date.today() - dt.timedelta(days=int(days * 1.5) + 2)).isoformat()
    url = ("https://data.colorado.gov/resource/4ykn-tg5h.json?$limit=5000&$where="
           + urllib.request.quote(f"entityformdate>='{since}' AND (principalcountry!='US' OR "
                                  f"entitytype in('FPC','FLLC','FLP','FNC'))"))
    rows = json.loads(get(url))
    out = []
    for r in rows:
        jur = (r.get("jurisdictonofformation") or "").strip()
        pc = (r.get("principalcountry") or "").upper()
        if len(jur) == 2 and jur.upper() in US_STATES and pc == "US":
            continue
        if jur in ("United States", "Cherokee Nation") or (jur.upper() in US_STATES and pc == "US"):
            continue
        city_state = (r.get("principalstate") or "").upper()
        if pc in EXCLUDED or jur.upper() in EXCLUDED:
            continue
        # "GE" with a US state is a data-entry artefact (Georgia the state, not the country)
        if pc == "GE" and city_state in US_STATES:
            continue
        if not (jur and jur.upper() not in US_STATES) and pc in ("", "US"):
            continue
        out.append({
            "source": "Colorado business registry",
            "signal_date": (r.get("entityformdate") or "")[:10],
            "company": r.get("entityname"),
            "hq_city": (r.get("principalcity") or "").title(),
            "hq_country": jur if jur and jur.upper() not in US_STATES else pc,
            "us_entity_state": "CO",
            "entity_type": r.get("entitytype"),
            "people": [],
            "filing_url": f"https://www.coloradosos.gov/biz/BusinessEntityDetail.do?quitButtonDestination=BusinessEntityResults&masterFileId={r.get('entityid')}",
            "signal": f"Registered a {r.get('entitytype')} in Colorado, formed in {jur or pc}",
        })
    log(f"colorado: {len(out)} foreign-formed / foreign-based registrations since {since}")
    return out


# --- Florida (Sunbiz daily filings over public SFTP; port 22 is open on GitHub runners) ---
# Layout per dos.fl.gov "Corporate File Definitions" (fixed width, 1-indexed in the spec).
FL = {"number": (0, 12), "name": (12, 204), "status": (204, 205), "type": (205, 220),
      "p_city": (304, 332), "p_state": (332, 334), "p_zip": (334, 344), "p_country": (344, 346),
      "file_date": (472, 480), "fei": (480, 494), "state_country": (503, 505)}
FL_OFFICER_START, FL_OFFICER_LEN = 668, 128
FL_COUNTRY_RX = re.compile(r"\\b(UNITED KINGDOM|ENGLAND|SCOTLAND|GERMANY|FRANCE|ITALY|SPAIN|PORTUGAL|NETHERLANDS|"
    r"BELGIUM|SWITZERLAND|AUSTRIA|SWEDEN|NORWAY|DENMARK|FINLAND|IRELAND|POLAND|ISRAEL|JAPAN|KOREA|TAIWAN|"
    r"CANADA|MEXICO|COLOMBIA|ARGENTINA|CHILE|PANAMA|COSTA RICA|ECUADOR|PARAGUAY|AUSTRALIA|NEW ZEALAND|"
    r"TURKEY|TURKIYE|UKRAINE|ROMANIA|BULGARIA|CROATIA|SERBIA|ESTONIA|LATVIA|LITHUANIA|LUXEMBOURG|SINGAPORE|"
    r"PHILIPPINES|THAILAND|JAMAICA|TRINIDAD|HONDURAS|MOROCCO|TUNISIA|EGYPT|JORDAN|PAKISTAN|ARMENIA|GEORGIA REP)\\b")
ISO_TREATY = set("AL AR AM AU AT AZ BH BD BE BA BG CM CA CL CO CR HR CZ DK EC EG EE ET FI FR GE DE GD "
                 "HN IE IL IT JM JP JO KZ KR XK KG LV LR LT LU MK MX MD MN ME MA NL NZ NO OM PK PA PY PH "
                 "PL PT RO SN RS SG SK SI ES LK SR SE CH TW TH TG TT TN TR UA GB UK".split())


def florida(days, log):
    try:
        import paramiko
    except ImportError:
        log("florida: paramiko not installed, skipped"); return []
    out = []
    try:
        import socket
        t = paramiko.Transport(socket.create_connection(("sftp.floridados.gov", 22), timeout=30))
        t.connect(username="Public", password="PubAccess1845!")
        sftp = paramiko.SFTPClient.from_transport(t)
    except Exception as e:
        log(f"florida: SFTP unreachable ({e.__class__.__name__}: {e})"); return []
    sample_logged = False
    for day in business_days(days):
        try:
            with sftp.open(f"doc/cor/{day:%Y%m%d}c.txt") as f:
                data = f.read()
        except Exception as e:
            log(f"florida {day}: no file ({e.__class__.__name__})"); continue
        lines = [l for l in data.split(b"\n") if l.strip()]
        log(f"florida {day}: {len(lines)} filings, record length {len(lines[0]) if lines else 0}")
        for raw in lines:
            line = raw.decode("latin-1")
            g = lambda k: line[FL[k][0]:FL[k][1]].strip()
            if not sample_logged:
                log("florida sample: " + json.dumps({k: g(k) for k in FL}))
                for rl in lines[:3]:
                    log("florida raw: " + json.dumps(rl.decode("latin-1")))
                sample_logged = True
            officers, foreign_officers = [], []
            for i in range(6):
                b = line[FL_OFFICER_START + i * FL_OFFICER_LEN: FL_OFFICER_START + (i + 1) * FL_OFFICER_LEN]
                if len(b) < 50 or not b.strip():
                    continue
                o = {"title": b[0:4].strip(), "name": b[5:47].strip(), "city": b[89:117].strip(),
                     "state": b[117:119].strip()}
                if o["name"]:
                    officers.append(o)
            pc, sc = g("p_country").upper(), g("state_country").upper()
            foreign_hq = pc and pc not in ("US", "") and pc in ISO_TREATY
            foreign_inc = len(sc) == 2 and sc not in US_STATES and sc in ISO_TREATY
            # Fallback while the address offsets are being confirmed: a treaty-country
            # name written anywhere in the record's address/officer area.
            m = FL_COUNTRY_RX.search(line[204:].upper())
            if not (foreign_hq or foreign_inc or m):
                continue
            if m and not (foreign_hq or foreign_inc):
                pc = m.group(1)
                foreign_hq = True
            out.append({
                "source": "Florida Sunbiz",
                "signal_date": str(day),
                "company": g("name"),
                "hq_city": g("p_city").title(),
                "hq_country": pc if foreign_hq else sc,
                "us_entity_state": "FL",
                "entity_type": g("type"),
                "people": [{"name": o["name"], "roles": [o["title"]]} for o in officers],
                "filing_url": "https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber?documentNumber=" + g("number"),
                "signal": "New Florida filing by a company based or formed in " + (pc if foreign_hq else sc),
            })
    try:
        sftp.close(); t.close()
    except Exception:
        pass
    log(f"florida: {len(out)} foreign-based / foreign-formed filings")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="business days to look back")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    log = lambda m: print(m, file=sys.stderr)
    codes = edgar_codes()
    res = florida(a.days, log) + form_d(a.days, codes, log) + colorado(a.days, log)
    seen, uniq = set(), []
    for c in res:
        k = re.sub(r"[^a-z0-9]", "", (c["company"] or "").lower())
        if k and k not in seen:
            seen.add(k); uniq.append(c)
    log(f"TOTAL candidates: {len(uniq)}")
    s = json.dumps(uniq, indent=1, ensure_ascii=False)
    (sys.stdout.write(s) if a.out == "-" else open(a.out, "w").write(s))


if __name__ == "__main__":
    main()
