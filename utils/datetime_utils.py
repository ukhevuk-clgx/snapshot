from datetime import UTC,datetime
def iso_timestamp(): return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
def file_timestamp(): return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
