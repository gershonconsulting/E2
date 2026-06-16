# scoring.py
# E-2 treaty-country detection and prospect scoring.
# Signal: a treaty-country address declared in the FL filing (principal or officer).
# We NEVER infer nationality from names — address only.

# E-2 Treaty countries (ISO 3166-1 alpha-2 and common name variants found in FL data)
# Source: https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/fees/treaty.html
TREATY_COUNTRIES = {
      # Europe
    "AL", "ALBANIA",
      "AM", "ARMENIA",
      "AT", "AUSTRIA",
      "AZ", "AZERBAIJAN",
      "BE", "BELGIUM",
      "BG", "BULGARIA",
      "BA", "BOSNIA",
      "HR", "CROATIA",
      "CY", "CYPRUS",
      "CZ", "CZECH REPUBLIC", "CZECHIA",
      "DK", "DENMARK",
      "EE", "ESTONIA",
      "FI", "FINLAND",
      "FR", "FRANCE",
      "GE", "GEORGIA",
      "DE", "GERMANY",
      "GR", "GREECE",
      "HU", "HUNGARY",
      "IE", "IRELAND",
      "IT", "ITALY",
      "KZ", "KAZAKHSTAN",
      "KG", "KYRGYZSTAN",
      "LV", "LATVIA",
      "LT", "LITHUANIA",
      "LU", "LUXEMBOURG",
      "MK", "NORTH MACEDONIA",
      "MT", "MALTA",
      "MD", "MOLDOVA",
      "ME", "MONTENEGRO",
      "NL", "NETHERLANDS",
      "NO", "NORWAY",
      "PL", "POLAND",
      "PT", "PORTUGAL",
      "RO", "ROMANIA",
      "RS", "SERBIA",
      "SK", "SLOVAKIA",
      "SI", "SLOVENIA",
      "ES", "SPAIN",
      "SE", "SWEDEN",
      "CH", "SWITZERLAND",
      "TJ", "TAJIKISTAN",
      "TR", "TURKEY", "TURKIYE",
      "TM", "TURKMENISTAN",
      "UA", "UKRAINE",
      "GB", "UK", "UNITED KINGDOM", "GREAT BRITAIN",
      "UZ", "UZBEKISTAN",
      # Americas
    "AG", "ANTIGUA", "ANTIGUA AND BARBUDA",
      "AR", "ARGENTINA",
      "BB", "BARBADOS",
      "BZ", "BELIZE",
      "BO", "BOLIVIA",
      "CA", "CANADA",
      "CL", "CHILE",
      "CO", "COLOMBIA",
      "CR", "COSTA RICA",
      "CW", "CURACAO",
      "DO", "DOMINICAN REPUBLIC",
      "EC", "ECUADOR",
      "SV", "EL SALVADOR",
      "GD", "GRENADA",
      "GT", "GUATEMALA",
      "HN", "HONDURAS",
      "JM", "JAMAICA",
      "MX", "MEXICO",
      "NI", "NICARAGUA",
      "PA", "PANAMA",
      "PY", "PARAGUAY",
      "PE", "PERU",
      "KN", "SAINT KITTS", "ST KITTS",
      "LC", "SAINT LUCIA", "ST LUCIA",
      "VC", "SAINT VINCENT", "ST VINCENT",
      "SR", "SURINAME",
      "TT", "TRINIDAD", "TRINIDAD AND TOBAGO",
      "UY", "URUGUAY",
      # Asia-Pacific
    "AU", "AUSTRALIA",
      "BD", "BANGLADESH",
      "KH", "CAMBODIA",
      "ET", "ETHIOPIA",
      "FJ", "FIJI",
      "ID", "INDONESIA",
      "IL", "ISRAEL",
      "JP", "JAPAN",
      "JO", "JORDAN",
      "KW", "KUWAIT",
      "LA", "LAOS",
      "LB", "LEBANON",
      "MY", "MALAYSIA",
      "MH", "MARSHALL ISLANDS",
      "FM", "MICRONESIA",
      "MN", "MONGOLIA",
      "MA", "MOROCCO",
      "NZ", "NEW ZEALAND",
      "OM", "OMAN",
      "PK", "PAKISTAN",
      "PW", "PALAU",
      "PH", "PHILIPPINES",
      "QA", "QATAR",
      "SA", "SAUDI ARABIA",
      "SG", "SINGAPORE",
      "KR", "SOUTH KOREA", "KOREA",
      "LK", "SRI LANKA",
      "TH", "THAILAND",
      "TN", "TUNISIA",
      "AE", "UAE", "UNITED ARAB EMIRATES",
      # Africa
    "CM", "CAMEROON",
      "CD", "CONGO", "DRC",
      "EG", "EGYPT",
      "GH", "GHANA",
      "KE", "KENYA",
      "LR", "LIBERIA",
      "MW", "MALAWI",
      "MR", "MAURITANIA",
      "MU", "MAURITIUS",
      "NA", "NAMIBIA",
      "SN", "SENEGAL",
      "ZA", "SOUTH AFRICA",
      "TZ", "TANZANIA",
      "TG", "TOGO",
}

# Countries explicitly excluded (not treaty; E-2 not available)
EXCLUDED_COUNTRIES = {
      "CN", "CHINA", "PEOPLES REPUBLIC OF CHINA",
      "IN", "INDIA",
      "BR", "BRAZIL",
      "RU", "RUSSIA", "RUSSIAN FEDERATION",
      "NG", "NIGERIA",
      "VN", "VIETNAM",
      "VE", "VENEZUELA",
      "MM", "MYANMAR", "BURMA",
      "CU", "CUBA",
      "IR", "IRAN",
      "KP", "NORTH KOREA",
      "SY", "SYRIA",
      "SD", "SUDAN",
}

DOMESTIC_STATES = {
      "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
      "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
      "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
      "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
      "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
      "DC","PR","VI","GU","AS","MP",
}


def _is_treaty(country_raw: str) -> bool:
      """Return True if country_raw maps to a treaty country."""
      c = country_raw.upper().strip()
      return bool(c and c in TREATY_COUNTRIES)


def _is_domestic(state_raw: str, country_raw: str) -> bool:
      """Return True if the address is clearly domestic (US state, blank country, or 'US'/'USA')."""
      state = state_raw.upper().strip()
      country = country_raw.upper().strip()
      if country in ("", "US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"):
                return True
            if state in DOMESTIC_STATES and not country:
                      return True
                  return False


def score_record(rec: dict) -> dict:
      """
          Score a parsed FL record for E-2 fit.
              Returns a dict with keys:
                      tier: "Qualified" | "Review" | "Filler" | "Excluded"
        reason: human-readable explanation
                treaty_country: the matched country string (or "")
                    """
    treaty_hit = ""
    reason = ""

    # Check principal address country first
    principal_country = rec.get("principal_country", "")
    principal_state   = rec.get("principal_state", "")

    if _is_treaty(principal_country):
              treaty_hit = principal_country
              reason = f"Principal address in treaty country: {principal_country}"

    # Check each officer's country
    if not treaty_hit:
              for off in rec.get("officers", []):
                            oc = off.get("officer_country", "")
                            if _is_treaty(oc):
                                              treaty_hit = oc
                                              reason = f"Officer '{off.get('officer_name','')}' address in treaty country: {oc}"
                                              break

                    # Explicit exclusion
                    pc_up = principal_country.upper()
    if pc_up in EXCLUDED_COUNTRIES:
              return {"tier": "Excluded", "reason": f"Non-treaty country: {principal_country}", "treaty_country": ""}
    for off in rec.get("officers", []):
              oc = off.get("officer_country", "").upper()
        if oc in EXCLUDED_COUNTRIES:
                      return {"tier": "Excluded", "reason": f"Officer from non-treaty country: {off.get('officer_country','')}", "treaty_country": ""}

    if treaty_hit:
              # Qualified = clear foreign treaty address, non-domestic principal
              if not _is_domestic(principal_state, principal_country):
                            return {"tier": "Qualified", "reason": reason, "treaty_country": treaty_hit}
else:
            return {"tier": "Review", "reason": reason + " (principal addr domestic)", "treaty_country": treaty_hit}

    # No treaty signal — filler (domestic or unknown)
    return {"tier": "Filler", "reason": "No treaty-country address signal", "treaty_country": ""}
