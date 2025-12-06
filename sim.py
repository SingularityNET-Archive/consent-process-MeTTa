#!/usr/bin/env python3
import json
import glob
import sys
import argparse
from hyperon import MeTTa

# ------------------------------------------------------------
# CLI Setup
# ------------------------------------------------------------
parser = argparse.ArgumentParser(description="MeTTa consent simulation")
parser.add_argument("folder", help="Folder containing proposal JSON files")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Show debugging/logging output")
args = parser.parse_args()


# ------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------
def log(*msg):
    if args.verbose:
        print("[LOG]", *msg)


# ------------------------------------------------------------
# Initialize MeTTa
# ------------------------------------------------------------
metta = MeTTa()


# ------------------------------------------------------------
# Load MeTTa rules
# ------------------------------------------------------------
def load_rules():
    rules = r'''
    ;; -----------------------------------------------------------------
    ;; Type Declarations
    ;; -----------------------------------------------------------------
    (: BudgetProposal P)
    (: Reviewer R)
    (: Objection O)

    ;; -----------------------------------------------------------------
    ;; Core Relations
    ;; -----------------------------------------------------------------
    (SubmittedBy P R)
    (ReviewedBy P R)

    ;; An objection is a structured object:
    ;; (Objection
    ;;      :id O
    ;;      :relevance REL
    ;;      :reason REASON
    ;;      :impact IMPACT
    ;;      :suggestion SUG)
    ;;
    (ObjectionRaised P O R)
    (ObjectionResolved P O)

    ;; -----------------------------------------------------------------
    ;; Derived Predicates
    ;; -----------------------------------------------------------------

    ;; A proposal has an unresolved objection if:
    ;; - an objection is raised for proposal P
    ;; - the same objection has NOT been resolved
    (HasUnresolvedObjection P) :-
        (ObjectionRaised P O R)
        (not (ObjectionResolved P O))

    ;; Consent = proposal exists AND there is NO unresolved objection.
    (HasConsent P) :-
        (BudgetProposal P)
        (not (HasUnresolvedObjection P))
    '''
    log("Loading rules...")
    metta.run(rules)
    log("Rules loaded.")


# ------------------------------------------------------------
# Convert a JSON proposal into MeTTa statements
# ------------------------------------------------------------
def load_proposal_json(path):
    with open(path) as f:
        data = json.load(f)

    log("\nParsing JSON:", path)
    log(json.dumps(data, indent=2))

    pid = data.get("id", "UnknownProposal")
    submitter = data.get("submitter", "UnknownSubmitter")
    reviewers = data.get("reviewers", [])
    objections = data.get("objections", [])

    stmts = []
    stmts.append(f"(BudgetProposal {pid})")
    stmts.append(f"(SubmittedBy {pid} {submitter})")

    for r in reviewers:
        stmts.append(f"(Reviewer {r})")
        stmts.append(f"(ReviewedBy {pid} {r})")

    for obj in objections:
        oid = obj["id"]
        reviewer = obj["reviewer"]

        relevance = obj.get("relevance", "\"none\"")
        reason = obj.get("reason", "\"none\"")
        impact = obj.get("impact", "\"none\"")
        suggestion = obj.get("suggestion", "\"none\"")

        # Encode objection as a structured MeTTa term
        stmts.append(
            f"(Objection "
            f":id {oid} "
            f":relevance \"{relevance}\" "
            f":reason \"{reason}\" "
            f":impact \"{impact}\" "
            f":suggestion \"{suggestion}\")"
        )

        # Link objection to proposal
        stmts.append(f"(ObjectionRaised {pid} {oid} {reviewer})")

        if obj.get("resolved", False):
            stmts.append(f"(ObjectionResolved {pid} {oid})")

    log("Generated MeTTa statements:")
    for s in stmts:
        log("  ", s)

    metta.run("\n".join(stmts))
    return pid


# ------------------------------------------------------------
# Evaluate consent
# ------------------------------------------------------------
def check_consent(pid):
    log(f"\nChecking consent for {pid} ...")
    result = metta.run(f"(HasConsent {pid})")

    log("Raw MeTTa result:", result)
    return bool(result)  # empty = False, non-empty = True


# ------------------------------------------------------------
# Simulation Driver
# ------------------------------------------------------------
def simulate(folder):
    load_rules()
    files = glob.glob(folder + "/*.json")
    if not files:
        print("No JSON files found in folder:", folder)
        return {}

    results = {}
    for f in files:
        pid = load_proposal_json(f)
        consent = check_consent(pid)
        results[pid] = consent

    return results


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if __name__ == "__main__":
    results = simulate(args.folder)
    print("\n===== CONSENT EVALUATION RESULTS =====")
    for pid, res in results.items():
        print(f"{pid:25} => {res}")
