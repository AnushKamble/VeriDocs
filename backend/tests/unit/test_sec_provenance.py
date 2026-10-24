from pathlib import Path
from veridocs.sec.provenance import FilingProvenance, compute_sha256


def test_provenance_save_load(temp_dir: Path):
    content = b"SEC filing raw bytes test string"
    sha = compute_sha256(content)

    prov = FilingProvenance(
        accession_number="0000320193-23-000106",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/sample.htm",
        raw_sha256=sha,
        byte_size=len(content),
        etag='"etag123"',
        http_status=200,
    )

    manifest_path = prov.save_manifest(temp_dir)
    assert manifest_path.exists()

    loaded = FilingProvenance.load_manifest(temp_dir)
    assert loaded is not None
    assert loaded.accession_number == prov.accession_number
    assert loaded.raw_sha256 == sha
    assert loaded.byte_size == len(content)
