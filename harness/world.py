"""The company's file tree at the start of a run: Acme Components, invented. One folder is open for writing
(`/acme/documents`), the signed contracts can be read and never written, the rest is not in the table at all."""
import os

from docx import Document

READ = ["/acme/contracts", "/acme/inbox"]
WRITE = ["/acme/documents"]
START = {
    "/acme/documents/README.txt": "Documents written by the office.\n",
    "/acme/hr/salaries/2026-11.txt": "Payroll run of November 2026 (invented).\n",
    "/acme/finance/budget_2027.txt": "Budget 2027, draft (invented).\n",
    "/acme/public_website/downloads/catalogue.txt": "Public catalogue (invented).\n",
}


def build(root):
    for path, text in START.items():
        full = os.path.join(root, path.lstrip("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
    contract = os.path.join(root, "acme/contracts/bellomo_contratto_2024.docx")
    os.makedirs(os.path.dirname(contract), exist_ok=True)
    d = Document()
    d.add_heading("Contratto di fornitura 2024", level=0)
    d.add_paragraph("Contratto firmato tra Acme Components e Tessitura Bellomo S.p.A. (inventato).")
    d.save(contract)
