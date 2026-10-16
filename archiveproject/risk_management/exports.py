"""Fill the original Excel package without rewriting its drawings or styles."""
from datetime import date, datetime
from io import BytesIO
from math import ceil
from pathlib import Path
import re
from xml.dom import minidom
from zipfile import ZIP_DEFLATED, ZipFile

from django.core import signing

from .models import RiskRegister


TEMPLATE = Path(__file__).parent / "report_templates" / "annual_risk_template.xlsx"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DOWNLOAD_MARK_SALT = "risk_management.download_provenance.v1"


class Formula:
    def __init__(self, expression, value):
        self.expression = expression
        self.value = value


def _elements(node, name):
    return [child for child in node.childNodes if child.nodeType == child.ELEMENT_NODE and child.localName == name]


def _column(number):
    name = ""
    while number:
        number, digit = divmod(number - 1, 26)
        name = chr(65 + digit) + name
    return name


def _column_number(address):
    number = 0
    for char in re.match(r"[A-Z]+", address).group():
        number = number * 26 + ord(char) - 64
    return number


def _append_text(document, parent, name, text):
    node = document.createElementNS(MAIN_NS, name)
    node.appendChild(document.createTextNode(str(text)))
    parent.appendChild(node)
    return node


class TemplateReport:
    def __init__(self):
        with ZipFile(TEMPLATE) as source:
            self.files = {name: source.read(name) for name in source.namelist()}
        self.book = minidom.parseString(self.files["xl/workbook.xml"])
        self.rels = minidom.parseString(self.files["xl/_rels/workbook.xml.rels"])
        self.types = minidom.parseString(self.files["[Content_Types].xml"])
        targets = {node.getAttribute("Id"): node.getAttribute("Target") for node in self.rels.getElementsByTagName("Relationship")}
        self.sheets = {}
        for sheet in self.book.getElementsByTagName("sheet"):
            target = targets[sheet.getAttributeNS(REL_NS, "id")]
            self.sheets[sheet.getAttribute("name")] = target.lstrip("/") if target.startswith("/") else "xl/" + target
        self.areas = {}

    def mark_download(self, provenance):
        """Embed signed provenance in Excel properties, outside all visible sheets."""
        custom_ns = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
        value_ns = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
        package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        root_rels = minidom.parseString(self.files["_rels/.rels"])
        relationship_type = REL_NS + "/custom-properties"
        relationship = next((node for node in root_rels.getElementsByTagName("Relationship")
                             if node.getAttribute("Type") == relationship_type), None)
        path = relationship.getAttribute("Target").lstrip("/") if relationship else "docProps/custom.xml"
        if path in self.files:
            properties = minidom.parseString(self.files[path])
        else:
            properties = minidom.getDOMImplementation().createDocument(custom_ns, "Properties", None)
            properties.documentElement.setAttribute("xmlns", custom_ns)
        properties.documentElement.setAttribute("xmlns:vt", value_ns)
        values = {
            "RiskDownloadID": provenance["download_id"],
            "RiskDownloadedBy": provenance["username"],
            "RiskDownloaderName": provenance["full_name"],
            "RiskDownloadedAt": provenance["downloaded_at"],
            "RiskDownloadProvenance": signing.dumps(provenance, salt=DOWNLOAD_MARK_SALT),
        }
        for node in list(properties.getElementsByTagName("property")):
            if node.getAttribute("name") in values:
                node.parentNode.removeChild(node)
        next_pid = max([1, *[int(node.getAttribute("pid")) for node in properties.getElementsByTagName("property")]]) + 1
        for offset, (name, value) in enumerate(values.items()):
            prop = properties.createElementNS(custom_ns, "property")
            for key, text in {"fmtid": "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}", "pid": str(next_pid + offset), "name": name}.items():
                prop.setAttribute(key, text)
            text_node = properties.createElementNS(value_ns, "vt:lpwstr")
            text_node.appendChild(properties.createTextNode(value))
            prop.appendChild(text_node)
            properties.documentElement.appendChild(prop)
        if relationship is None:
            relationship = root_rels.createElementNS(package_ns, "Relationship")
            existing_ids = {node.getAttribute("Id") for node in root_rels.getElementsByTagName("Relationship")}
            rel_id = "rIdRiskDownloadProperties"
            while rel_id in existing_ids:
                rel_id += "_"
            for key, value in {"Id": rel_id, "Type": relationship_type, "Target": path}.items():
                relationship.setAttribute(key, value)
            root_rels.documentElement.appendChild(relationship)
        if not any(node.getAttribute("PartName") == "/" + path for node in self.types.getElementsByTagName("Override")):
            override = self.types.createElement("Override")
            override.setAttribute("PartName", "/" + path)
            override.setAttribute("ContentType", "application/vnd.openxmlformats-officedocument.custom-properties+xml")
            self.types.documentElement.appendChild(override)
        self.files[path] = properties.toxml(encoding="UTF-8")
        self.files["_rels/.rels"] = root_rels.toxml(encoding="UTF-8")

    def add_fourth_quarter(self):
        source_path = self.sheets["Pemantauan TW 3"]
        target_path = "xl/worksheets/sheet11.xml"
        self.files[target_path] = self.files[source_path]
        source_rels = "xl/worksheets/_rels/" + source_path.rsplit("/", 1)[-1] + ".rels"
        if source_rels in self.files:
            self.files["xl/worksheets/_rels/sheet11.xml.rels"] = self.files[source_rels]
        sheets = self.book.getElementsByTagName("sheets")[0]
        sheet = self.book.createElementNS(MAIN_NS, "sheet")
        sheet.setAttribute("name", "Pemantauan TW4")
        sheet.setAttribute("sheetId", "22")
        sheet.setAttributeNS(REL_NS, "r:id", "rIdAnnualTW4")
        sheets.insertBefore(sheet, sheets.lastChild)
        rel = self.rels.createElement("Relationship")
        for key, value in {"Id": "rIdAnnualTW4", "Type": REL_NS + "/worksheet", "Target": "worksheets/sheet11.xml"}.items():
            rel.setAttribute(key, value)
        self.rels.documentElement.appendChild(rel)
        override = self.types.createElement("Override")
        override.setAttribute("PartName", "/" + target_path)
        override.setAttribute("ContentType", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
        self.types.documentElement.appendChild(override)
        self.sheets["Pemantauan TW4"] = target_path

    def fill(self, name, records, columns, *, metadata=None, start=10):
        path = self.sheets[name]
        document = minidom.parseString(self.files[path])
        data = document.getElementsByTagName("sheetData")[0]
        rows = {int(row.getAttribute("r")): row for row in _elements(data, "row")}
        cells = {cell.getAttribute("r"): cell for row in rows.values() for cell in _elements(row, "c")}
        samples = {col: cells.get(f"{_column(col)}{start}") for col in range(1, columns + 1)}
        styles = {col: sample.getAttribute("s") if sample else "" for col, sample in samples.items()}
        for address, cell in list(cells.items()):
            if int(re.search(r"\d+", address).group()) >= start and _column_number(address) <= columns:
                for child in list(cell.childNodes):
                    cell.removeChild(child)
                if cell.hasAttribute("t"):
                    cell.removeAttribute("t")

        def write(address, value):
            row_number = int(re.search(r"\d+", address).group())
            col = _column_number(address)
            if row_number not in rows:
                row = document.createElementNS(MAIN_NS, "row")
                row.setAttribute("r", str(row_number))
                following = next((r for number, r in sorted(rows.items()) if number > row_number), None)
                data.insertBefore(row, following)
                rows[row_number] = row
            row = rows[row_number]
            cell = cells.get(address)
            if cell is None:
                cell = document.createElementNS(MAIN_NS, "c")
                cell.setAttribute("r", address)
                if styles.get(col):
                    cell.setAttribute("s", styles[col])
                following = next((c for c in _elements(row, "c") if _column_number(c.getAttribute("r")) > col), None)
                row.insertBefore(cell, following)
                cells[address] = cell
            if row_number >= start and styles.get(col):
                cell.setAttribute("s", styles[col])
            if name == "Analisis & Evaluasi Risiko" and col in (4, 5, 6) and value == "ü":
                cell.setAttribute("s", styles[5])
            for child in list(cell.childNodes):
                cell.removeChild(child)
            if cell.hasAttribute("t"):
                cell.removeAttribute("t")
            if value is None or value == "":
                return
            if isinstance(value, Formula):
                _append_text(document, cell, "f", value.expression.lstrip("="))
                if isinstance(value.value, str):
                    cell.setAttribute("t", "str")
                _append_text(document, cell, "v", value.value)
            elif isinstance(value, (date, datetime)):
                day = value.date() if isinstance(value, datetime) else value
                _append_text(document, cell, "v", (day - date(1899, 12, 30)).days)
            elif isinstance(value, (int, float)):
                _append_text(document, cell, "v", value)
            else:
                text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))
                if len(text) > 32767:
                    from django.core.exceptions import ValidationError
                    raise ValidationError("Teks laporan melebihi batas Excel 32.767 karakter per sel.")
                cell.setAttribute("t", "inlineStr")
                inline = document.createElementNS(MAIN_NS, "is")
                cell.appendChild(inline)
                node = _append_text(document, inline, "t", text)
                node.setAttribute("xml:space", "preserve")

        if metadata:
            for address, value in metadata.items():
                write(address, value)
                if isinstance(value, str) and "\n" in value:
                    row_number = int(re.search(r"\d+", address).group())
                    rows[row_number].setAttribute("ht", str(min(409, 15 * len(value.splitlines()))))
                    rows[row_number].setAttribute("customHeight", "1")
        widths = {}
        for node in document.getElementsByTagName("col"):
            for col in range(int(node.getAttribute("min")), min(columns, int(node.getAttribute("max"))) + 1):
                widths[col] = float(node.getAttribute("width") or 10)
        for offset, record in enumerate(records):
            row_number = start + offset
            record = record(row_number) if callable(record) else record
            height = 24
            for col, value in enumerate(record, 1):
                write(f"{_column(col)}{row_number}", value)
                if isinstance(value, str):
                    lines = sum(max(1, ceil(len(line) / max(5, widths.get(col, 15) - 1))) for line in value.split("\n"))
                    height = max(height, lines * 14 + 8)
            rows[row_number].setAttribute("ht", str(min(409, height)))
            rows[row_number].setAttribute("customHeight", "1")
        last = max(start, start + len(records) - 1)
        self.areas[name] = f"$A$1:${_column(columns)}${last}"
        # Remove comments about the template's sample records, preserving header notes.
        relpath = "xl/worksheets/_rels/" + path.rsplit("/", 1)[-1] + ".rels"
        if relpath in self.files:
            relationships = minidom.parseString(self.files[relpath])
            for rel in relationships.getElementsByTagName("Relationship"):
                if rel.getAttribute("Type").endswith("/comments"):
                    import posixpath
                    comments_path = posixpath.normpath(posixpath.join("xl/worksheets", rel.getAttribute("Target")))
                    if comments_path in self.files:
                        comments = minidom.parseString(self.files[comments_path])
                        for comment in list(comments.getElementsByTagName("comment")):
                            if int(re.search(r"\d+", comment.getAttribute("ref")).group()) >= start:
                                comment.parentNode.removeChild(comment)
                        self.files[comments_path] = comments.toxml(encoding="UTF-8")
        dimension = document.getElementsByTagName("dimension")
        if dimension:
            dimension[0].setAttribute("ref", f"A1:{_column(max(columns, 20))}{max(last, max(rows))}")
        self.files[path] = document.toxml(encoding="UTF-8")

    def save(self):
        names = self.book.getElementsByTagName("definedNames")[0]
        sheets = list(self.book.getElementsByTagName("sheet"))
        for index, sheet in enumerate(sheets):
            name = sheet.getAttribute("name")
            if name not in self.areas:
                continue
            for node in list(_elements(names, "definedName")):
                if node.getAttribute("localSheetId") == str(index):
                    names.removeChild(node)
            area = self.book.createElementNS(MAIN_NS, "definedName")
            area.setAttribute("name", "_xlnm.Print_Area")
            area.setAttribute("localSheetId", str(index))
            area.appendChild(self.book.createTextNode(f"'{name}'!{self.areas[name]}"))
            names.appendChild(area)
        for node in self.book.getElementsByTagName("calcPr"):
            node.setAttribute("fullCalcOnLoad", "1")
            node.setAttribute("forceFullCalc", "1")
        for node in list(self.rels.getElementsByTagName("Relationship")):
            if node.getAttribute("Type").endswith("/calcChain"):
                node.parentNode.removeChild(node)
        for node in list(self.types.getElementsByTagName("Override")):
            if node.getAttribute("PartName") == "/xl/calcChain.xml":
                node.parentNode.removeChild(node)
        self.files.pop("xl/calcChain.xml", None)
        self.files["xl/workbook.xml"] = self.book.toxml(encoding="UTF-8")
        self.files["xl/_rels/workbook.xml.rels"] = self.rels.toxml(encoding="UTF-8")
        self.files["[Content_Types].xml"] = self.types.toxml(encoding="UTF-8")
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as destination:
            for name, content in self.files.items():
                destination.writestr(name, content)
        output.seek(0)
        return output


def _risk_values(likelihood, impact, likelihood_column, impact_column, row):
    if likelihood is None or impact is None:
        return [likelihood, impact, None, None]
    score = likelihood * impact
    score_col = _column(_column_number(impact_column) + 1)
    score_ref = f"{score_col}{row}"
    level_formula = f'IF({score_ref}>=17,"Sangat Tinggi",IF({score_ref}>=10,"Tinggi",IF({score_ref}>=5,"Sedang",IF({score_ref}>=3,"Rendah","Sangat Rendah"))))'
    return [likelihood, impact, Formula(f"{likelihood_column}{row}*{impact_column}{row}", score), Formula(level_formula, RiskRegister.level_for(score))]


def annual_risk_workbook(risks, *, division, year, download_mark=None):
    report = TemplateReport()
    risks = list(risks)
    metadata = {
        "C4": division.name,
        "C5": "\n".join(dict.fromkeys(r.risk_owner for r in risks if r.risk_owner)),
        "C6": "\n".join(dict.fromkeys(r.risk_officer for r in risks if r.risk_officer)),
    }
    identification, evaluation, treatments = [], [], []
    quarter_records = {quarter: [] for quarter in range(1, 5)}
    for number, risk in enumerate(risks, 1):
        lines = [text.splitlines() or [""] for text in (
            risk.strategic_objective, risk.indication or risk.description, risk.cause, risk.impact,
        )]
        for index in range(max(map(len, lines))):
            parts = [values[index] if index < len(values) else "" for values in lines]
            identification.append(lambda row, n=number, r=risk, p=parts, first=index == 0: [
                n if first else None, p[0], r.title if first else None, p[1], p[2],
                r.get_controllability_display() if r.controllability and p[2] else "", p[3],
                *(_risk_values(r.inherent_likelihood, r.inherent_impact, "H", "I", row) if first else [None] * 4),
                r.identification_notes if first else None,
            ])
        for index, control in enumerate(risk.existing_controls.splitlines() or [""]):
            evaluation.append(lambda row, n=number, r=risk, c=control, first=index == 0: [
                n if first else None, r.title if first else None, c,
                *["ü" if r.control_effectiveness == value else "" for value in ("ineffective", "adequate", "effective")],
                *(_risk_values(r.residual_likelihood, r.residual_impact, "G", "H", row) if first else [None] * 4),
                "✓" if r.is_priority and first else "", r.evaluation_notes if first else None,
            ])
        for index, treatment in enumerate(risk.treatments.all()):
            treatments.append(lambda row, n=number, r=risk, t=treatment, first=index == 0: [
                n if first else None, r.title if first else None, t.option, t.action_plan,
                *_risk_values(t.expected_likelihood, t.expected_impact, "E", "F", row),
                t.target_date, t.responsible_person, t.notes,
            ])
        for monitoring in risk.monitorings.all():
            if monitoring.year != year:
                continue
            actions = list(monitoring.action_plans.all()) or [None]
            for index, action in enumerate(actions):
                def monitoring_row(row, m=monitoring, a=action, first=index == 0, n=number, r=risk):
                    values = [n if first else None, r.title if first else None,
                              a.description if a else None, a.realization if a else None,
                              a.target_date if a else None, a.responsible_person if a else None]
                    if first:
                        values += _risk_values(m.initial_likelihood, m.initial_impact, "G", "H", row)
                        values += _risk_values(m.final_likelihood, m.final_impact, "K", "L", row)
                        values += _risk_values(m.expected_likelihood, m.expected_impact, "O", "P", row)
                        values += [Formula(f"Q{row}-M{row}", m.deviation) if m.deviation is not None else None,
                                   "\n".join(filter(None, [m.evaluation_notes, m.business_environment_changes]))]
                    else:
                        values += [None] * 14
                    return values
                quarter_records[monitoring.quarter].append(monitoring_row)
    report.fill("Identifikasi Risiko", identification, 12, metadata=metadata)
    report.fill("Analisis & Evaluasi Risiko", evaluation, 12, metadata=metadata)
    report.fill("Perlakuan Risiko", treatments, 11, metadata=metadata)
    for quarter, name in [(1, "Pemantauan TW1"), (2, "Pemantauan TW2"), (3, "Pemantauan TW 3")]:
        report.fill(name, quarter_records[quarter], 20, metadata=metadata)
    if quarter_records[4]:
        report.add_fourth_quarter()
        report.fill("Pemantauan TW4", quarter_records[4], 20, metadata=metadata)
    # This system has no incidental-report records; return the original blank form.
    report.fill("Pelaporan Insidental", [], 17, start=7)
    if download_mark is not None:
        report.mark_download(download_mark)
    return report.save()
