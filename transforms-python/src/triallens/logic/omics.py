"""Omics domain: sample manifest, targeted genotypes, APOE haplotypes."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from triallens.reference import APOE_RS429358, APOE_RS7412
from triallens.utils.columns import clean_str, code_key, map_values, parse_bool, parse_date, parse_decimal, upper_str

ASSAY_TYPE_MAP = {
    "RNASEQ": "RNASEQ", "RNA": "RNASEQ", "MRNASEQ": "RNASEQ",
    "WGS": "WGS", "WHOLEGENOME": "WGS", "WHOLEGENOMESEQUENCING": "WGS",
    "GENOTYPINGARRAY": "GENOTYPING_ARRAY", "SNPARRAY": "GENOTYPING_ARRAY", "GSA": "GENOTYPING_ARRAY",
    "PROTEOMICS": "PROTEOMICS", "OLINK": "PROTEOMICS", "SOMASCAN": "PROTEOMICS",
}

RSID_PATTERN = r"^rs[0-9]+$"
GENOTYPE_PATTERN = r"^[ACGT]/[ACGT]$"


def clean_omics_samples(manifest: DataFrame) -> DataFrame:
    md5 = F.lower(clean_str("file_md5"))
    uri = clean_str("file_uri")
    reads = parse_decimal("read_count").cast("long")
    typed = manifest.select(
        upper_str("omics_sample_id").alias("omics_sample_id"),
        upper_str("specimen_barcode").alias("specimen_id"),
        map_values(code_key("assay_type"), ASSAY_TYPE_MAP).alias("assay_type"),
        clean_str("sequencing_run_id").alias("sequencing_run_id"),
        upper_str("flowcell").alias("flowcell"),
        clean_str("instrument").alias("instrument"),
        parse_date("run_date").alias("run_date"),
        F.when((reads >= 0) & (reads <= 10_000_000_000), reads).alias("read_count"),
        # Missing QC information is treated as a failed QC.
        F.coalesce(parse_bool("qc_pass"), F.lit(False)).alias("qc_pass"),
        F.when(uri.rlike("^(s3|gs|abfss|file)://.+"), uri).alias("file_uri"),
        F.when(md5.rlike("^[0-9a-f]{32}$"), md5).alias("file_md5"),
    ).where(
        F.col("omics_sample_id").isNotNull() & F.col("specimen_id").isNotNull() & F.col("assay_type").isNotNull()
    )
    return typed.dropDuplicates(["omics_sample_id"])


def clean_omics_genotypes(genotypes: DataFrame) -> DataFrame:
    raw = F.regexp_replace(F.regexp_replace(upper_str("genotype"), r"\s", ""), r"\|", "/")
    # Unphased representation with alleles in lexical order: "T/C" -> "C/T".
    genotype = F.when(raw.rlike(GENOTYPE_PATTERN), F.concat_ws("/", F.array_sort(F.split(raw, "/"))))
    quality = parse_decimal("quality")
    typed = genotypes.select(
        clean_str("call_id").alias("call_id"),
        upper_str("omics_sample_id").alias("omics_sample_id"),
        upper_str("gene").alias("gene"),
        F.lower(clean_str("variant_id")).alias("variant_id"),
        genotype.alias("genotype"),
        F.when((quality >= 0) & (quality <= 100), quality).alias("quality"),
    ).where(
        F.col("call_id").isNotNull()
        & F.col("omics_sample_id").isNotNull()
        & F.col("variant_id").rlike(RSID_PATTERN)
        & F.col("genotype").isNotNull()
    )
    return typed.dropDuplicates(["call_id"])


def curate_omics_samples(samples: DataFrame, specimens: DataFrame) -> DataFrame:
    """Attach omics samples to patients via the biobank specimen they were derived from."""
    return samples.join(specimens.select("specimen_id", "patient_id"), "specimen_id", "inner").select(
        "omics_sample_id",
        "specimen_id",
        "patient_id",
        "assay_type",
        "sequencing_run_id",
        "flowcell",
        "instrument",
        "run_date",
        "read_count",
        "qc_pass",
        "file_uri",
        "file_md5",
    )


def derive_apoe(genotypes: DataFrame, omics_samples: DataFrame) -> DataFrame:
    """APOE haplotype per patient from rs429358 and rs7412.

    e4 alleles = number of C alleles at rs429358, e2 alleles = number of T alleles at
    rs7412, the rest are e3. Returns patient_id, apoe_genotype (e.g. ``e3/e4``) and
    apoe_e4_carrier. Ambiguous combinations (e.g. e1) yield NULL.
    """
    calls = (
        genotypes.where(F.col("variant_id").isin(APOE_RS429358, APOE_RS7412))
        .join(omics_samples.where(F.col("qc_pass")).select("omics_sample_id", "patient_id"), "omics_sample_id")
        .groupBy("patient_id")
        .agg(
            F.max(F.when(F.col("variant_id") == APOE_RS429358, F.col("genotype"))).alias("g_rs429358"),
            F.max(F.when(F.col("variant_id") == APOE_RS7412, F.col("genotype"))).alias("g_rs7412"),
        )
        .where(F.col("g_rs429358").isNotNull() & F.col("g_rs7412").isNotNull())
    )
    counted = calls.select(
        "patient_id",
        F.expr("size(filter(split(g_rs429358, '/'), a -> a = 'C'))").alias("n_e4"),
        F.expr("size(filter(split(g_rs7412, '/'), a -> a = 'T'))").alias("n_e2"),
    ).withColumn("n_e3", F.lit(2) - F.col("n_e4") - F.col("n_e2"))

    alleles = F.expr("concat_ws('/', concat(array_repeat('e2', n_e2), array_repeat('e3', n_e3), array_repeat('e4', n_e4)))")
    return counted.select(
        "patient_id",
        F.when(F.col("n_e3") >= 0, alleles).alias("apoe_genotype"),
        F.when(F.col("n_e3") >= 0, F.col("n_e4") > 0).alias("apoe_e4_carrier"),
    )
