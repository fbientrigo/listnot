"""Identity core — the privacy boundary.

A Chilean RUT may transit this package *in memory only*: it is normalized,
validated, and converted to a keyed HMAC pseudonym, then discarded. No function
here returns, logs, or embeds a raw RUT (docs/PRIVACY_MODEL.md §3, §8).
"""

from pucv_aq_qc.identity import hmac_id, rut
from pucv_aq_qc.identity.exceptions import InvalidRUTError, MissingSecretError

__all__ = ["rut", "hmac_id", "InvalidRUTError", "MissingSecretError"]
