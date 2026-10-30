"""Deterministic synthetic extracts for the 14 TrialLens sources.

Everything generated here is fictitious. The generator deliberately reproduces the
heterogeneity of real extracts so that the clean layer is exercised: mixed ISO and
German date formats, decimal commas, censored lab values, code spelling variants,
unit variants (ng/mL vs pg/mL), duplicate records, re-processed imaging measures,
failed assay runs, late CSF processing and the occasional unusable row.

Usage: ``python -m triallens.local.synthetic --out data/raw --patients 200 --seed 7``
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from triallens.config import load_sources

LAST_DATE = date(2025, 12, 31)

GROUP_WEIGHTS = {
    "ALZHEIMERS": 30, "MCI": 25, "FTD": 8, "DLB": 6, "PARKINSONS": 10, "ALS": 4, "CONTROL": 17,
}
AMYLOID_POSITIVE_PROBABILITY = {
    "ALZHEIMERS": 0.92, "MCI": 0.5, "FTD": 0.1, "DLB": 0.45, "PARKINSONS": 0.15, "ALS": 0.1, "CONTROL": 0.15,
}
PRIMARY_ICD = {
    "ALZHEIMERS": ["G30.1", "G301", "g30.0", "F00.1*"],
    "MCI": ["F06.7", "F067"],
    "FTD": ["G31.0", "G310"],
    "DLB": ["G31.82"],
    "PARKINSONS": ["G20", "G20.9"],
    "ALS": ["G12.2", "G122"],
    "CONTROL": [],
}
COMORBID_ICD = ["I10", "E11.9", "E78.0", "F32.1", "I48.0", "M17.1", "H40.1"]

GROUP_MEDICATIONS = {
    "ALZHEIMERS": [("N06DA02", "donepezil", ["5", "10"]), ("N06DX01", "memantine", ["10", "20"])],
    "MCI": [("N06DA04", "galantamine", ["8", "16"])],
    "DLB": [("N06DA03", "rivastigmine", ["4,6", "9,5"])],
    "PARKINSONS": [("N04BA02", "levodopa/carbidopa", ["100", "200"])],
    "ALS": [("N07XX02", "riluzole", ["50"])],
    "FTD": [("N06AB06", "sertraline", ["50", "100"])],
    "CONTROL": [],
}
COMORBID_MEDICATIONS = [
    ("C09AA05", "ramipril", ["2,5", "5"]),
    ("A10BA02", "metformin", ["500", "1000"]),
    ("C10AA05", "atorvastatin", ["20", "40"]),
    ("B01AC06", "acetylsalicylic acid", ["100"]),
]

SITES = [
    ("SITE-N", "Northern Memory Clinic"),
    ("SITE-S", "Southern Neurology Centre"),
    ("SITE-W", "Western University Hospital"),
]
STUDIES = {
    "TL-001": ("Longitudinal Neurodegeneration Biomarker Cohort", "Observational", ["COHORT"]),
    "TL-002": ("Plasma p-tau217 Diagnostic Accuracy Study", "Diagnostic", ["DIAGNOSTIC"]),
    "TL-003": ("Disease-Modifying Therapy Extension Trial", "Phase 3", ["ACTIVE", "PLACEBO"]),
}

LAB_TESTS = [
    # loinc, name, unit, low, high, normal_low, normal_high
    ("4548-4", "Hemoglobin A1c", "%", 4.6, 8.2, 4.0, 5.6),
    ("2160-0", "Creatinine", "mg/dL", 0.6, 1.7, 0.6, 1.3),
    ("2132-9", "Vitamin B12", "pg/mL", 150, 950, 200, 900),
    ("3016-3", "TSH", "mIU/L", 0.2, 5.5, 0.4, 4.0),
    ("2345-7", "Glucose", "mg/dL", 72, 150, 70, 99),
    ("13457-7", "LDL Cholesterol", "mg/dL", 60, 190, 0, 130),
    ("718-7", "Hemoglobin", "g/dL", 11.0, 17.0, 12.0, 16.0),
    ("2951-2", "Sodium", "mmol/L", 133, 147, 135, 145),
]

# analyte -> (raw spellings, matrix, lloq pg/mL, uloq pg/mL, (neg_low, neg_high), (pos_low, pos_high))
ASSAYS = {
    "ABETA42": (["Abeta42", "AB42", "Abeta1-42", "ABETA42"], "CSF", 200, 1700, (1000, 1900), (350, 900)),
    "ABETA40": (["Abeta40", "AB40", "Abeta1-40"], "CSF", 1000, 40000, (8000, 16000), (8000, 16000)),
    "PTAU181": (["pTau181", "p-tau181", "P-TAU181"], "CSF", 8, 120, (12, 24), (25, 60)),
    "TTAU": (["t-tau", "tTau", "Total tau"], "CSF", 80, 1300, (150, 290), (300, 700)),
    "NFL": (["NfL", "NFL", "Nf-L"], "PLASMA", 0.5, 500, (6, 22), (8, 30)),
    "GFAP": (["GFAP"], "PLASMA", 5, 1000, (60, 180), (150, 350)),
    "PTAU217": (["pTau217", "p-tau217"], "PLASMA", 0.05, 10, (0.1, 0.38), (0.45, 1.4)),
}
CSF_PANEL = ["ABETA42", "ABETA40", "PTAU181", "TTAU"]
PLASMA_PANEL = ["NFL", "GFAP", "PTAU217"]

MRI_SCANNERS = [
    ("SN-45021", "SIEMENS Healthineers", "3.0"),
    ("SN-77810", "Siemens", "3"),
    ("GE-55102", "GE MEDICAL SYSTEMS", "3.0"),
    ("PH-30117", "Philips Medical Systems", "1,5"),
]
PET_SCANNER = ("SN-PET-1104", "Siemens", "")

APOE_WEIGHTS_DEFAULT = {"e3/e3": 58, "e3/e4": 22, "e4/e4": 3, "e2/e3": 13, "e2/e4": 2, "e2/e2": 2}
APOE_WEIGHTS_AD = {"e3/e3": 35, "e3/e4": 42, "e4/e4": 14, "e2/e3": 5, "e2/e4": 3, "e2/e2": 1}
RS429358 = {"e2": "T", "e3": "T", "e4": "C"}
RS7412 = {"e2": "T", "e3": "C", "e4": "C"}

VISIT_OFFSETS = [("BL", 0), ("M06", 182), ("M12", 365), ("M24", 730)]
VISIT_SPELLINGS = {
    "BL": ["BL", "Baseline", "V0"],
    "M06": ["M06", "M6", "m-06"],
    "M12": ["M12", "m12"],
    "M24": ["M24", "M-24"],
}


class Generator:
    def __init__(self, n_patients: int, seed: int) -> None:
        self.n_patients = n_patients
        self.rng = random.Random(seed)
        self.rows: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.ids: dict[str, itertools.count] = defaultdict(lambda: itertools.count(1))
        self.runs: dict[tuple[str, str], tuple[str, str]] = {}

    # ---------------------------------------------------------------- helpers
    def next_id(self, prefix: str, width: int = 7) -> str:
        return f"{prefix}{next(self.ids[prefix]):0{width}d}"

    def maybe(self, probability: float) -> bool:
        return self.rng.random() < probability

    def fmt_date(self, d: date | None) -> str:
        if d is None:
            return ""
        fmt = self.rng.choice(["%Y-%m-%d", "%Y-%m-%d", "%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"])
        return d.strftime(fmt)

    def fmt_ts(self, ts: datetime | None) -> str:
        if ts is None:
            return ""
        fmt = self.rng.choice(["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"])
        return ts.strftime(fmt)

    def fmt_num(self, value: float, digits: int = 2, comma_probability: float = 0.2) -> str:
        text = f"{round(value, digits)}"
        return text.replace(".", ",") if self.maybe(comma_probability) else text

    def mrn_variant(self, mrn: str) -> str:
        return self.rng.choice([mrn, mrn, mrn, mrn.lower(), f" {mrn} "])

    def add(self, source: str, **row: str) -> None:
        self.rows[source].append({k: ("" if v is None else str(v)) for k, v in row.items()})

    # --------------------------------------------------------------- patients
    def generate(self) -> dict[str, list[dict[str, str]]]:
        for i in range(self.n_patients):
            self.patient(i)
        return self.rows

    def patient(self, index: int) -> None:
        rng = self.rng
        mrn = f"MRN{1_000_000 + index}"
        group = rng.choices(list(GROUP_WEIGHTS), weights=list(GROUP_WEIGHTS.values()))[0]
        amyloid_positive = self.maybe(AMYLOID_POSITIVE_PROBABILITY[group])
        site_code, site_name = rng.choice(SITES)
        birth = date(rng.randint(1938, 1972), rng.randint(1, 12), rng.randint(1, 28))
        baseline = date(rng.randint(2019, 2023), rng.randint(1, 12), rng.randint(1, 28))
        visits = [(code, baseline + timedelta(days=offset)) for code, offset in VISIT_OFFSETS
                  if baseline + timedelta(days=offset) <= LAST_DATE and (offset == 0 or self.maybe(0.85))]
        deceased = baseline + timedelta(days=rng.randint(400, 900)) if self.maybe(0.03) else None

        self.demographics(mrn, birth, site_code, deceased)
        encounters = self.encounters(mrn, visits, site_code)
        self.diagnoses(mrn, group, encounters)
        self.medications(mrn, group, baseline)
        self.cognition(mrn, group, visits)
        self.biosamples(mrn, group, amyloid_positive, visits)
        self.imaging(mrn, group, amyloid_positive, visits)
        self.study(mrn, group, amyloid_positive, baseline, site_code, site_name)

    def demographics(self, mrn: str, birth: date, site_code: str, deceased: date | None) -> None:
        rng = self.rng
        sex = rng.choice(["M", "F", "male", "female", "W", "weiblich", "1", "2"] * 10 + ["D"])
        postal = f"{rng.randint(1067, 99998):05d}"
        updated = datetime(2025, rng.randint(1, 12), rng.randint(1, 28), rng.randint(6, 20), rng.randint(0, 59))
        row = dict(
            mrn=self.mrn_variant(mrn), sex=sex, birth_date=self.fmt_date(birth), postal_code=postal,
            ethnicity=rng.choice(["White", "Asian", "Black", "Other", "Unknown", ""]),
            deceased_date=self.fmt_date(deceased), site_code=rng.choice([site_code, site_code.lower()]),
            last_updated=self.fmt_ts(updated),
        )
        if self.maybe(0.08):  # stale duplicate from an earlier extract
            stale = dict(row, postal_code=f"{rng.randint(1067, 99998):05d}", last_updated=self.fmt_ts(updated - timedelta(days=200)))
            self.add("ehr_patients", **stale)
        self.add("ehr_patients", **row)

    def encounters(self, mrn: str, visits: list[tuple[str, date]], site_code: str) -> list[tuple[str, datetime]]:
        rng = self.rng
        result = []
        for _, visit_date in visits:
            admit = datetime.combine(visit_date, datetime.min.time()) + timedelta(hours=rng.randint(8, 15))
            encounter_id = self.next_id("E")
            self.add("ehr_encounters", encounter_id=encounter_id, mrn=self.mrn_variant(mrn),
                     encounter_type=rng.choice(["OUTPATIENT", "AMB", "ambulant", "Outpatient"]),
                     admit_ts=self.fmt_ts(admit), discharge_ts=self.fmt_ts(admit + timedelta(hours=2)),
                     site_code=site_code, department="Memory Clinic")
            result.append((encounter_id, admit))
        for _ in range(rng.randint(0, 2)):
            admit = datetime.combine(visits[0][1], datetime.min.time()) + timedelta(days=rng.randint(10, 700), hours=rng.randint(0, 23))
            encounter_type = rng.choice(["INPATIENT", "STAT", "EMERGENCY", "ER", "TELEHEALTH", "Video"])
            if encounter_type in ("INPATIENT", "STAT"):
                discharge = admit + timedelta(days=rng.randint(1, 21))
            else:
                discharge = admit + timedelta(hours=rng.randint(1, 6))
            if self.maybe(0.03):  # EHR artefact: discharge recorded before admission
                discharge = admit - timedelta(hours=3)
            encounter_id = self.next_id("E")
            self.add("ehr_encounters", encounter_id=encounter_id, mrn=self.mrn_variant(mrn), encounter_type=encounter_type,
                     admit_ts=self.fmt_ts(admit), discharge_ts=self.fmt_ts(discharge), site_code=site_code,
                     department=rng.choice(["Neurology", "Internal Medicine", "Emergency Department", "Geriatrics"]))
            result.append((encounter_id, admit))
        if self.maybe(0.02):  # unusable row without patient reference
            self.add("ehr_encounters", encounter_id=self.next_id("E"), mrn="", encounter_type="AMB",
                     admit_ts=self.fmt_ts(datetime(2024, 1, 2, 9)), discharge_ts="", site_code=site_code, department="")
        return result

    def diagnoses(self, mrn: str, group: str, encounters: list[tuple[str, datetime]]) -> None:
        rng = self.rng
        if PRIMARY_ICD[group]:
            encounter_id, admit = encounters[0]
            self.add("ehr_diagnoses", diagnosis_id=self.next_id("D"), encounter_id=encounter_id, mrn=self.mrn_variant(mrn),
                     icd10_code=rng.choice(PRIMARY_ICD[group]), diagnosis_date=self.fmt_date(admit.date()),
                     is_primary=rng.choice(["Y", "J", "1", "true"]))
        for _ in range(rng.randint(0, 3)):
            encounter_id, admit = rng.choice(encounters)
            self.add("ehr_diagnoses", diagnosis_id=self.next_id("D"), encounter_id=encounter_id, mrn=self.mrn_variant(mrn),
                     icd10_code=rng.choice(COMORBID_ICD), diagnosis_date=self.fmt_date(admit.date()),
                     is_primary=rng.choice(["N", "0", "false", ""]))

    def medications(self, mrn: str, group: str, baseline: date) -> None:
        rng = self.rng
        candidates = list(GROUP_MEDICATIONS[group]) + rng.sample(COMORBID_MEDICATIONS, rng.randint(0, 2))
        for atc, name, doses in candidates:
            start = baseline + timedelta(days=rng.randint(0, 200))
            end = start + timedelta(days=rng.randint(90, 900)) if self.maybe(0.4) else None
            self.add("ehr_medications", medication_id=self.next_id("MED"), mrn=self.mrn_variant(mrn),
                     atc_code=rng.choice([atc, atc.lower(), f"{atc[:4]} {atc[4:]}"]),
                     drug_name=rng.choice([name, name.upper()]), start_date=self.fmt_date(start),
                     end_date=self.fmt_date(end), dose_mg=rng.choice(doses), route=rng.choice(["oral", "PO", "transdermal"]))

    # -------------------------------------------------------------- cognition
    def cognition(self, mrn: str, group: str, visits: list[tuple[str, date]]) -> None:
        rng = self.rng
        severity = {"CONTROL": 0.0, "MCI": 0.35, "PARKINSONS": 0.25, "ALS": 0.15, "FTD": 0.6, "DLB": 0.6, "ALZHEIMERS": 0.8}[group]
        for visit_index, (visit_code, visit_date) in enumerate(visits):
            decline = severity * (1 + 0.15 * visit_index)
            scores = {
                "MMSE": max(0, min(30, round(29.5 - 12 * decline + rng.gauss(0, 1.2)))),
                "MOCA": max(0, min(30, round(28 - 13 * decline + rng.gauss(0, 1.5)))),
                "CDR_SB": max(0.0, min(18.0, round((8 * decline + rng.gauss(0, 0.6)) * 2) / 2)),
            }
            if group in ("ALZHEIMERS", "MCI") and visit_code in ("BL", "M12"):
                scores["ADAS_COG13"] = max(0, min(85, round(9 + 35 * decline + rng.gauss(0, 3))))
            spellings = {"MMSE": ["MMSE", "MMST"], "MOCA": ["MoCA", "MOCA"], "CDR_SB": ["CDR-SB", "CDR SB"],
                         "ADAS_COG13": ["ADAS-Cog13", "ADAS13"]}
            rater = f"R{rng.randint(1, 12):03d}"
            for instrument, score in scores.items():
                raw_score = self.fmt_num(score, 1, 0.3) if instrument == "CDR_SB" else str(score)
                if instrument == "MMSE" and self.maybe(0.01):
                    raw_score = "34"  # out of scale: data-entry error, dropped by the clean layer
                self.add("cognitive_assessments", assessment_id=self.next_id("CA"), mrn=self.mrn_variant(mrn),
                         visit_code=rng.choice(VISIT_SPELLINGS[visit_code]), instrument=rng.choice(spellings[instrument]),
                         score=raw_score, assessed_date=self.fmt_date(visit_date), rater_id=rater)

    # ------------------------------------------------------------- biosamples
    def specimen(self, mrn: str, barcode: str, parent: str, specimen_type: str, collected: datetime,
                 received: datetime, volume: float, status: str, stored: bool, shipment: str = "") -> None:
        rng = self.rng
        freezer = rack = box = position = ""
        if stored:
            freezer = rng.choice(["FRZ-01", "FRZ-02", "FRZ-03", "frz-04"])
            rack = f"R{rng.randint(1, 9):02d}"
            box = f"B{rng.randint(1, 40):03d}"
            position = f"{rng.choice('ABCDEFGHI')}{rng.randint(1, 9)}"
        self.add("lims_specimens", specimen_barcode=barcode, parent_barcode=parent, mrn=self.mrn_variant(mrn),
                 specimen_type=specimen_type, collected_ts=self.fmt_ts(collected), received_ts=self.fmt_ts(received),
                 freezer_id=freezer, rack=rack, box=box, position=position, volume_ul=self.fmt_num(volume, 0, 0.0),
                 shipment_id=shipment, status=status)

    def aliquot_status(self) -> tuple[str, str]:
        status = self.rng.choice(["AVAILABLE", "IN_STORAGE", "Stored", "AVAILABLE", "RESERVED", "SHIPPED", "DEPLETED"])
        shipment = f"SHP-{self.rng.randint(1, 25):04d}" if status == "SHIPPED" or self.maybe(0.1) else ""
        return status, shipment

    def run_for(self, platform_key: str, day: date) -> tuple[str, str]:
        key = (platform_key, day.strftime("%Y%m"))
        if key not in self.runs:
            self.runs[key] = (f"RUN-{key[1]}-{platform_key}", f"PL-{key[1]}-{self.rng.randint(1, 9)}")
        return self.runs[key]

    def assay(self, specimen_barcode: str, analyte: str, amyloid_positive: bool, group: str, run_day: date) -> None:
        rng = self.rng
        spellings, matrix, lloq, uloq, negative, positive = ASSAYS[analyte]
        low, high = positive if amyloid_positive else negative
        if analyte == "NFL" and group in ("ALS", "FTD"):
            low, high = 40, 150
        value = rng.uniform(low, high)
        platform = rng.choice(["Lumipulse G1200", "Elecsys cobas e601"]) if matrix == "CSF" else "Simoa HD-X"
        run_id, plate_id = self.run_for(platform.split()[0].upper(), run_day)
        unit, factor = "pg/mL", 1.0
        if analyte in ("ABETA42", "ABETA40"):
            unit, factor = rng.choice([("pg/mL", 1.0), ("pg/mL", 1.0), ("ng/mL", 0.001), ("ng/L", 1.0)])
        digits = 3 if analyte == "PTAU217" else 1
        if factor != 1.0:
            digits = 5
        qc = rng.choices(["PASS", "OK", "passed", "WARN", "FAIL", "failed"], weights=[60, 15, 15, 5, 3, 2])[0]
        self.add("biomarker_assays", assay_result_id=self.next_id("BA"), specimen_barcode=specimen_barcode,
                 run_id=run_id, plate_id=plate_id, platform=platform, analyte=rng.choice(spellings),
                 value=self.fmt_num(value * factor, digits, 0.15), unit=unit,
                 lloq=f"{lloq * factor:g}", uloq=f"{uloq * factor:g}", run_date=self.fmt_date(run_day), qc_status=qc)

    def labs(self, mrn: str, specimen_barcode: str, collected: datetime) -> None:
        rng = self.rng
        for loinc, name, unit, low, high, normal_low, normal_high in rng.sample(LAB_TESTS, rng.randint(3, 6)):
            value = rng.uniform(low, high)
            flag = "H" if value > normal_high else "L" if value < normal_low else rng.choice(["N", ""])
            raw_value = self.fmt_num(value, 2, 0.25)
            if loinc == "3016-3" and self.maybe(0.05):
                raw_value, flag = "<0,01", "L"  # censored below the detection limit
            if self.maybe(0.01):
                raw_value = "n/a"  # unusable row, dropped by the clean layer
            self.add("lab_results", result_id=self.next_id("LR"), mrn=self.mrn_variant(mrn), specimen_barcode=specimen_barcode,
                     loinc_code=loinc, test_name=name, value=raw_value, unit=unit, collected_ts=self.fmt_ts(collected),
                     resulted_ts=self.fmt_ts(collected + timedelta(hours=rng.randint(2, 30))), abnormal_flag=flag)

    def biosamples(self, mrn: str, group: str, amyloid_positive: bool, visits: list[tuple[str, date]]) -> None:
        rng = self.rng
        for visit_code, visit_date in visits:
            if visit_code == "M06":
                continue
            collected = datetime.combine(visit_date, datetime.min.time()) + timedelta(hours=8, minutes=rng.randint(0, 120))
            run_day = min(visit_date + timedelta(days=rng.randint(7, 60)), LAST_DATE)

            # Serum for routine labs
            serum = self.next_id("SPC")
            self.specimen(mrn, serum, "", rng.choice(["Serum", "SERUM"]), collected,
                          collected + timedelta(hours=rng.uniform(0.5, 4)), rng.uniform(1500, 4000), "AVAILABLE", True)
            self.labs(mrn, serum, collected)

            # EDTA plasma -> aliquots -> plasma biomarker panel
            plasma = self.next_id("SPC")
            received = collected + timedelta(hours=rng.uniform(0.5, 3) if not self.maybe(0.02) else rng.uniform(26, 40))
            self.specimen(mrn, plasma, "", rng.choice(["EDTA plasma", "Plasma", "EDTA_PLASMA"]), collected, received,
                          rng.uniform(3000, 6000), rng.choice(["CONSUMED", "DEPLETED"]), False)
            for k in (1, 2):
                status, shipment = self.aliquot_status()
                self.specimen(mrn, f"{plasma}-A{k}", plasma, "Plasma", collected, received, rng.uniform(250, 500),
                              status, True, shipment)
            for analyte in PLASMA_PANEL:
                self.assay(f"{plasma}-A1", analyte, amyloid_positive, group, run_day)

            # CSF (lumbar puncture) -> aliquot -> CSF core panel
            if self.maybe(0.5 if visit_code == "BL" else 0.25):
                csf = self.next_id("SPC")
                delay = rng.uniform(0.3, 1.8) if self.maybe(0.85) else rng.uniform(2.5, 6)
                received = collected + timedelta(hours=delay)
                self.specimen(mrn, csf, "", rng.choice(["CSF", "Liquor"]), collected, received, rng.uniform(8000, 12000),
                              "CONSUMED", False)
                for k in (1, 2, 3):
                    status, shipment = self.aliquot_status()
                    self.specimen(mrn, f"{csf}-A{k}", csf, "CSF", collected, received, rng.uniform(400, 500), status, True, shipment)
                for analyte in CSF_PANEL:
                    self.assay(f"{csf}-A1", analyte, amyloid_positive, group, run_day)

            # Whole blood at baseline -> DNA (genotyping) and optionally RNA (RNA-seq)
            if visit_code == "BL":
                blood = self.next_id("SPC")
                received = collected + timedelta(hours=rng.uniform(1, 8))
                self.specimen(mrn, blood, "", rng.choice(["Whole blood", "EDTA blood"]), collected, received,
                              rng.uniform(8000, 10000), "CONSUMED", False)
                self.specimen(mrn, f"{blood}-DNA", blood, "DNA", collected, received, rng.uniform(100, 200), "AVAILABLE", True)
                self.genotyping(f"{blood}-DNA", group, run_day)
                if self.maybe(0.3):
                    self.specimen(mrn, f"{blood}-RNA", blood, rng.choice(["RNA", "PAXgene RNA"]), collected, received,
                                  rng.uniform(50, 120), "AVAILABLE", True)
                    self.rnaseq(f"{blood}-RNA", run_day)

    # ------------------------------------------------------------------ omics
    def md5(self) -> str:
        digest = f"{self.rng.getrandbits(128):032x}"
        return digest.upper() if self.maybe(0.02) else digest

    def genotyping(self, specimen_barcode: str, group: str, run_day: date) -> None:
        rng = self.rng
        sample_id = self.next_id("OMX", 6)
        run_number = (run_day.year - 2019) * 12 + run_day.month
        qc_pass = rng.choice(["true", "TRUE", "1", "yes"]) if self.maybe(0.95) else "false"
        self.add("omics_sample_manifest", omics_sample_id=sample_id, specimen_barcode=specimen_barcode,
                 assay_type=rng.choice(["SNP-Array", "GSA", "Genotyping array"]), sequencing_run_id=f"GT-RUN-{run_number:03d}",
                 flowcell="", instrument="iScan", run_date=self.fmt_date(run_day), read_count="", qc_pass=qc_pass,
                 file_uri=f"s3://triallens-omics/genotyping/{sample_id}.idat", file_md5=self.md5())
        weights = APOE_WEIGHTS_AD if group in ("ALZHEIMERS", "MCI") else APOE_WEIGHTS_DEFAULT
        a1, a2 = rng.choices(list(weights), weights=list(weights.values()))[0].split("/")
        calls = [
            ("APOE", "rs429358", RS429358[a1], RS429358[a2]),
            ("APOE", "rs7412", RS7412[a1], RS7412[a2]),
            ("TREM2", "rs75932628", "C", rng.choice(["C"] * 30 + ["T"])),
            ("PICALM", "rs3851179", rng.choice("CT"), rng.choice("CT")),
        ]
        for gene, rsid, x, y in calls:
            if self.maybe(0.5):
                x, y = y, x
            self.add("omics_genotypes", call_id=self.next_id("GC", 8), omics_sample_id=sample_id,
                     gene=rng.choice([gene, gene.lower()]), variant_id=rsid,
                     genotype=f"{x}{rng.choice(['/', '|'])}{y}", quality=self.fmt_num(rng.uniform(30, 99), 1, 0.0))

    def rnaseq(self, specimen_barcode: str, run_day: date) -> None:
        rng = self.rng
        sample_id = self.next_id("OMX", 6)
        run_number = (run_day.year - 2019) * 4 + (run_day.month - 1) // 3
        self.add("omics_sample_manifest", omics_sample_id=sample_id, specimen_barcode=specimen_barcode,
                 assay_type=rng.choice(["RNA-Seq", "RNAseq"]), sequencing_run_id=f"NS-RUN-{run_number:03d}",
                 flowcell=f"H{rng.randint(1000, 9999)}DSX5", instrument="NovaSeq 6000", run_date=self.fmt_date(run_day),
                 read_count=str(rng.randint(18_000_000, 65_000_000)),
                 qc_pass="true" if self.maybe(0.93) else "false",
                 file_uri=f"s3://triallens-omics/rnaseq/{sample_id}.fastq.gz", file_md5=self.md5())

    # ---------------------------------------------------------------- imaging
    def imaging(self, mrn: str, group: str, amyloid_positive: bool, visits: list[tuple[str, date]]) -> None:
        rng = self.rng
        atrophy = {"ALZHEIMERS": 0.75, "MCI": 0.88, "FTD": 0.8, "DLB": 0.85}.get(group, 1.0)
        scanner = rng.choice(MRI_SCANNERS)
        for visit_code, visit_date in visits:
            if visit_code == "M06" or not self.maybe(0.7 if visit_code == "BL" else 0.4):
                continue
            study_uid = f"1.2.826.0.1.3680043.8.498.{next(self.ids['study_uid'])}"
            for k, (description, instances, thickness) in enumerate(
                [("T1 MPRAGE sag", rng.randint(176, 192), "1.0"), ("FLAIR ax", rng.randint(48, 60), "3.0")], start=1
            ):
                series_uid = f"{study_uid}.{k}"
                self.add("imaging_dicom_metadata", study_instance_uid=study_uid, series_instance_uid=series_uid,
                         mrn=self.mrn_variant(mrn), modality=rng.choice(["MR", "MRI"]), series_description=description,
                         acquisition_date=self.fmt_date(visit_date), scanner_serial=scanner[0], manufacturer=scanner[1],
                         field_strength_t=scanner[2], slice_thickness_mm=thickness, num_instances=str(instances))
                if k == 1 and self.maybe(0.95):
                    self.volumetrics(series_uid, atrophy, visit_date)

            if visit_code == "BL" and self.maybe(0.35):
                study_uid = f"1.2.826.0.1.3680043.8.498.{next(self.ids['study_uid'])}"
                series_uid = f"{study_uid}.1"
                pet_date = visit_date + timedelta(days=rng.randint(1, 30))
                self.add("imaging_dicom_metadata", study_instance_uid=study_uid, series_instance_uid=series_uid,
                         mrn=self.mrn_variant(mrn), modality=rng.choice(["PT", "PET"]),
                         series_description="Amyloid PET florbetaben", acquisition_date=self.fmt_date(pet_date),
                         scanner_serial=PET_SCANNER[0], manufacturer=PET_SCANNER[1], field_strength_t=PET_SCANNER[2],
                         slice_thickness_mm="2.0", num_instances=str(rng.randint(90, 110)))
                suvr = rng.uniform(1.2, 2.1) if amyloid_positive else rng.uniform(0.9, 1.08)
                self.measure(series_uid, rng.choice(["COMPOSITE", "composite"]), "SUVR", suvr, "v1.2.0",
                             datetime.combine(pet_date, datetime.min.time()) + timedelta(days=3))

    def volumetrics(self, series_uid: str, atrophy: float, visit_date: date) -> None:
        rng = self.rng
        computed = datetime.combine(visit_date, datetime.min.time()) + timedelta(days=rng.randint(1, 14))
        versions = [("v2.3.1", computed)]
        if self.maybe(0.2):  # re-processed with a newer pipeline version; the latest computation wins
            versions.append(("v2.4.0", computed + timedelta(days=120)))
        for version, computed_ts in versions:
            raw_version = version.upper() if self.maybe(0.1) else version
            for region in ("Hippocampus L", "Hippocampus R"):
                volume = rng.uniform(3300, 4300) * atrophy
                self.measure(series_uid, rng.choice([region, region.upper().replace(" ", "_")]),
                             rng.choice(["VOLUME", "volume_mm3"]), volume, raw_version, computed_ts)
            self.measure(series_uid, "Cortex mean", rng.choice(["THICKNESS", "CORTICAL_THICKNESS_MM"]),
                         rng.uniform(2.2, 2.8) * (0.5 + atrophy / 2), raw_version, computed_ts)

    def measure(self, series_uid: str, region: str, metric: str, value: float, version: str, computed: datetime) -> None:
        self.add("imaging_derived_measures", measure_id=self.next_id("IM"), series_instance_uid=series_uid, region=region,
                 metric=metric, value=self.fmt_num(value, 3, 0.1), pipeline_version=version, computed_ts=self.fmt_ts(computed))

    # ------------------------------------------------------------------ study
    def study(self, mrn: str, group: str, amyloid_positive: bool, baseline: date, site_code: str, site_name: str) -> None:
        rng = self.rng
        studies = ["TL-001"]
        if group in ("ALZHEIMERS", "MCI", "CONTROL") and self.maybe(0.4):
            studies.append("TL-002")
        if group in ("ALZHEIMERS", "MCI") and amyloid_positive and self.maybe(0.35):
            studies.append("TL-003")
        for study_code in studies:
            title, phase, arms = STUDIES[study_code]
            enrolled = baseline - timedelta(days=rng.randint(0, 20))
            if study_code == "TL-003":
                status = rng.choice(["Enrolled", "RANDOMIZED", "Screening", "Screen fail", "Withdrawn"])
            else:
                status = rng.choices(["Enrolled", "ACTIVE", "Completed", "Withdrawn", "dropped"], weights=[45, 15, 25, 10, 5])[0]
            withdrawn = enrolled + timedelta(days=rng.randint(60, 600)) if status in ("Withdrawn", "dropped") else None
            self.add("ctms_enrollment", enrollment_id=self.next_id("ENR", 6), mrn=self.mrn_variant(mrn),
                     study_code=rng.choice([study_code, study_code.replace("-", ""), study_code.lower()]),
                     study_title=title, study_phase=phase, arm=rng.choice(arms), site_code=site_code, site_name=site_name,
                     enrolled_date=self.fmt_date(enrolled), status=status, withdrawn_date=self.fmt_date(withdrawn))
            self.consents(mrn, study_code, enrolled)

    def consents(self, mrn: str, study_code: str, enrolled: date) -> None:
        rng = self.rng
        spellings = {
            "CLINICAL_DATA": ["Clinical data", "CLINICAL_DATA", "clinical"],
            "BIOSAMPLES": ["Biosamples", "samples", "BIOBANK"],
            "GENETICS": ["Genetics", "genetic"],
            "IMAGING": ["Imaging"],
            "RECONTACT": ["Recontact", "Re-contact"],
        }
        grant_probability = {"CLINICAL_DATA": 0.995, "BIOSAMPLES": 0.98, "GENETICS": 0.8, "IMAGING": 0.75, "RECONTACT": 0.6}
        signed = enrolled - timedelta(days=rng.randint(1, 10))
        for scope, options in spellings.items():
            granted = self.maybe(grant_probability[scope])
            withdrawn = None
            if granted and scope == "GENETICS" and self.maybe(0.04):
                withdrawn = signed + timedelta(days=rng.randint(100, 500))
            self.add("consent_registry", consent_id=self.next_id("CNS"), mrn=self.mrn_variant(mrn),
                     study_code=rng.choice([study_code, study_code.replace("-", "")]),
                     consent_version=rng.choice(["v2.1", "2.1", "V2.1"]), scope=rng.choice(options),
                     granted=rng.choice(["Y", "yes", "J", "1", "true"]) if granted else rng.choice(["N", "no", "0"]),
                     signed_date=self.fmt_date(signed), withdrawn_date=self.fmt_date(withdrawn))
        if self.maybe(0.1):  # re-consent to a new version supersedes the earlier clinical-data consent
            self.add("consent_registry", consent_id=self.next_id("CNS"), mrn=self.mrn_variant(mrn), study_code=study_code,
                     consent_version="v3.0", scope="CLINICAL_DATA", granted="Y",
                     signed_date=self.fmt_date(signed + timedelta(days=rng.randint(200, 700))), withdrawn_date="")


def write_csvs(rows: dict[str, list[dict[str, str]]], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for source in load_sources():
        name, columns = source["name"], source["columns"]
        with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows.get(name, []))
        counts[name] = len(rows.get(name, []))
    return counts


def generate(out_dir: Path | str, n_patients: int = 200, seed: int = 7) -> dict[str, int]:
    rows = Generator(n_patients, seed).generate()
    return write_csvs(rows, Path(out_dir))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic TrialLens source extracts.")
    parser.add_argument("--out", default="data/raw")
    parser.add_argument("--patients", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    for name, count in generate(args.out, args.patients, args.seed).items():
        print(f"{name:28s} {count:>7d} rows")


if __name__ == "__main__":
    main()
