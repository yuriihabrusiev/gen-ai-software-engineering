"""Transaction processing pipeline stages.

Each stage (validator, fraud_detector, compliance_checker) is a standalone
module exposing `process_transaction(record: dict) -> dict`. Stages never
import or call each other directly — all inter-stage communication happens
through the file-based protocol in `shared/{input,processing,output,results}/`
(see `pipeline.common` for the shared helpers and `specification.md` for the
full protocol definition).
"""
