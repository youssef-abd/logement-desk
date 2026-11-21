"""Detect shared-flat (colocation) listings from the title and description. A hint: the desk shows a badge."""
import re

# "colocation autorisée / possible / non acceptée" in an ordinary flat is the landlord's rule, not a shared flat
_COLOC_WORD = re.compile(r"\bcolocation\b|\bcoloc\b|\bcolocataires?\b", re.I)
_RULE = re.compile(r"(?:colocation|coloc)s?\s+(?:non\s+|pas\s+)?(?:autoris|accept|possible|interdit|refus|admis)|(?:pas|non|sans|interdit)\s+(?:de\s+|d.)?(?:colocation|coloc)", re.I)
_SHARED = re.compile(
    r"chambre\s+(?:meubl[ée]e?\s+)?(?:dans|au sein d|en)\s+(?:un\s+|une\s+)?(?:appartement|logement|maison|colocation|coloc)"
    r"|chambres?\s+(?:disponibles?|libres?)\b|\d\s*chambres?\s+(?:disponibles?|[àa]\s+louer)"
    r"|(?:cuisine|salon|salle de bains?|sdb)\s+partag[ée]e?s?|parties?\s+communes?\s+(?:partag|avec)|appartement\s+partag[ée]"
    r"|loyer\s+par\s+chambre|(?:chambre|loyer)\s+(?:en|de)\s+colocation", re.I)


def _get(l, key):
    return l.get(key) if isinstance(l, dict) else getattr(l, key, None)


def is_coloc(l):
    text = f"{_get(l, 'title') or ''}\n{_get(l, 'description') or ''}"
    if _SHARED.search(text):
        return True
    return bool(_COLOC_WORD.search(_RULE.sub(" ", text)))
