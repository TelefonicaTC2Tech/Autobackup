

def parse_number_selection(selection: str) -> set[int]:
        """
        Parse a comma-and-dash separated selection string into a set of ints.

        Supports formats like:
        - "3"      → {3}
        - "1,4,6"  → {1,4,6}
        - "2-5"    → {2,3,4,5}
        - "1,3-5"  → {1,3,4,5}

        Ignores invalid entries.
        """
        out = set()
        for part in filter(None, (p.strip() for p in selection.split(","))):
            if "-" in part:
                try:
                    a, b = part.split("-", 1)
                    start, end = int(a), int(b)
                    if start >= end:                   
                        raise ValueError(
                            f"Invalid range format {start}-{end}, the second element must be greater than the first one."
                        )
                except ValueError as e:
                    raise e
                out.update(range(start, end + 1))
            else:
                try:
                    out.add(int(part))
                except ValueError as e:
                    raise e
        return out