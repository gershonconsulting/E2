# field_spec.py
# Florida Division of Corporations COR fixed-width layout
# Reference: https://dos.sunbiz.org/data-definitions/cor.html
# IMPORTANT: Verify these offsets against a real file using:
#   python3 florida_pipeline.py --inspect <filename>
# before trusting output in production.

# Each entry: (field_name, start_byte, end_byte) [0-indexed, end exclusive]
FIELD_SPEC = [
    ("document_number",   0,   12),
        ("state_of_inc",     12,   14),
            ("type_code",        14,   17),
                ("status",           17,   21),
                    ("principal_addr1",  21,   61),
                        ("principal_city",   61,   81),
                            ("principal_state",  81,   83),
                                ("principal_zip",    83,   93),
                                    ("principal_country",93,  101),
                                        ("mailing_addr1",   101,  141),
                                            ("mailing_city",    141,  161),
                                                ("mailing_state",   161,  163),
                                                    ("mailing_zip",     163,  173),
                                                        ("mailing_country", 173,  181),
                                                            ("reg_agent_name",  181,  221),
                                                                ("reg_agent_addr",  221,  261),
                                                                    ("corp_name",       261,  361),
                                                                        ("date_filed",      361,  369),
                                                                            ("last_event",      369,  379),
                                                                                ("event_date",      379,  387),
                                                                                ]

                                                                                # Officer/director repeating blocks begin here
                                                                                OFFICER_TAIL_START = 387
                                                                                OFFICER_BLOCK_SIZE = 100
                                                                                OFFICER_FIELDS = [
                                                                                    ("officer_name",     0,  30),
                                                                                        ("officer_title",   30,  34),
                                                                                            ("officer_addr",    34,  74),
                                                                                                ("officer_city",    74,  89),
                                                                                                    ("officer_state",   89,  91),
                                                                                                        ("officer_zip",     91,  99),
                                                                                                            ("officer_country", 99, 100),
                                                                                                            ]
                                                                                                            
                                                                                                            RECORD_LENGTH = 487  # approximate; verify with --inspect
                                                                                                            
                                                                                                            
                                                                                                            def parse_record(line: bytes) -> dict:
                                                                                                                """Parse one fixed-width COR record into a dict. All values stripped."""
                                                                                                                    rec = {}
                                                                                                                        for name, start, end in FIELD_SPEC:
                                                                                                                                chunk = line[start:end] if end <= len(line) else line[start:]
                                                                                                                                        rec[name] = chunk.decode("latin-1").strip()
                                                                                                                                        
                                                                                                                                            # Convenience: expose principal_country at top level for scorer
                                                                                                                                                rec["principal_country"] = rec.get("principal_country", "")
                                                                                                                                                
                                                                                                                                                    # Parse officer blocks
                                                                                                                                                        rec["officers"] = []
                                                                                                                                                            tail = line[OFFICER_TAIL_START:]
                                                                                                                                                                offset = 0
                                                                                                                                                                    while offset + OFFICER_BLOCK_SIZE <= len(tail):
                                                                                                                                                                            block = tail[offset: offset + OFFICER_BLOCK_SIZE]
                                                                                                                                                                                    officer = {}
                                                                                                                                                                                            for fname, s, e in OFFICER_FIELDS:
                                                                                                                                                                                                        raw = block[s:e] if e <= len(block) else b""
                                                                                                                                                                                                                    officer[fname] = raw.decode("latin-1").strip()
                                                                                                                                                                                                                            if officer.get("officer_name"):
                                                                                                                                                                                                                                        rec["officers"].append(officer)
                                                                                                                                                                                                                                                offset += OFFICER_BLOCK_SIZE
                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                    return rec
                                                                                                                                                                                                                                                    
