"""A larger synthetic docx (many paragraphs) purely to give the
interrupt/resume test enough wall-clock time to actually interrupt
mid-run -- the small test_input.docx finishes before a kill signal
can land.
"""

from docx import Document

SAMPLE_LINES = [
    "kṛṣṇaḥ sarva-kāraṇa-kāraṇam",
    "śrī-guruṁ caraṇāravinde nimittam apy uddhava",
    "tatra sarva iti gatam api uddhava tathā ca",
    "yathā pāde nirṇītam iti śāstra-vacanāt",
    "This is a plain English paragraph that should be skipped.",
    "sac-cid-ānanda-vigrahaḥ paramātmā parameśvaraḥ",
]


def main():
    document = Document()
    for i in range(300):
        document.add_paragraph(SAMPLE_LINES[i % len(SAMPLE_LINES)])
    document.save("test_big.docx")
    print("wrote test_big.docx with 300 paragraphs")


if __name__ == "__main__":
    main()
