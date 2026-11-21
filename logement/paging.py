from .errors import Blocked


def collect(get_page, max_pages, size, id_of, sleep=None, pause=0):
    """Fetch up to max_pages pages (get_page(0), get_page(1)...), de-duplicated by id.

    Stops on a short page. A Blocked on a later page returns what was already collected;
    on the first page it propagates."""
    out, seen = [], set()
    for n in range(max_pages):
        if n and sleep and pause:
            sleep(pause)
        try:
            page = get_page(n)
        except Blocked:
            if n == 0:
                raise
            break
        for item in page:
            k = id_of(item)
            if k not in seen:
                seen.add(k)
                out.append(item)
        if len(page) < size:
            break
    return out
