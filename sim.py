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
# Canonical Python store of facts for deterministic checks
# { pid: { "raised": set((oid, reviewer)), "resolved": set(oid) } }
# ------------------------------------------------------------
proposal_facts = {}


# ------------------------------------------------------------
# Canonical MeTTa rules
# ------------------------------------------------------------
CANONICAL_RULES = r'''
;; ---------- canonical rules ----------
(: BudgetProposal P)
(: Proposal P)
(: Objection O)
(: Reviewer R)

(SubmittedBy P R)
(ReviewedBy P R)

;; canonical objection facts:
(ObjectionRaised P O R)
(ObjectionResolved P O)

;; derived predicate (kept for informational queries)
(HasUnresolvedObjection P) :-
    (ObjectionRaised P O R)
    (not (ObjectionResolved P O))

(HasConsent P) :-
    (BudgetProposal P)
    (not (HasUnresolvedObjection P))
;; ------------------------------------
'''


# ------------------------------------------------------------
# Initialize MeTTa
# ------------------------------------------------------------
metta = MeTTa()


# ------------------------------------------------------------
# Load MeTTa rules
# ------------------------------------------------------------
def load_rules():
    log("Loading rules...")
    metta.run(CANONICAL_RULES)
    log("Rules loaded.")


# ------------------------------------------------------------
# Python-side deterministic consent check functions
# ------------------------------------------------------------
def python_has_unresolved(pid):
    """Deterministic check for unresolved objections using Python facts."""
    facts = proposal_facts.get(pid, {"raised": set(), "resolved": set()})
    raised_oids = {oid for (oid, _) in facts["raised"]}
    unresolved = raised_oids - facts["resolved"]
    return len(unresolved) > 0

def python_has_consent(pid):
    """Deterministic check for consent: consent when there are NO unresolved objections."""
    return not python_has_unresolved(pid)


# ------------------------------------------------------------
# Convert a JSON proposal into MeTTa statements and record facts
# ------------------------------------------------------------
def assert_proposal_and_record(path):
    with open(path) as f:
        data = json.load(f)

    log("\nParsing JSON:", path)
    if args.verbose:
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

    # Prepare Python canonical store
    if pid not in proposal_facts:
        proposal_facts[pid] = {"raised": set(), "resolved": set()}

    for obj in objections:
        oid = obj.get("id")
        reviewer = obj.get("reviewer", "UnknownReviewer")

        # Assert canonical MeTTa facts: (ObjectionRaised P O R)
        stmts.append(f"(ObjectionRaised {pid} {oid} {reviewer})")

        if obj.get("resolved", False):
            stmts.append(f"(ObjectionResolved {pid} {oid})")
            proposal_facts[pid]["resolved"].add(oid)
        else:
            proposal_facts[pid]["raised"].add((oid, reviewer))

    log("Generated MeTTa statements:")
    for s in stmts:
        log("  ", s)

    # Assert statements into MeTTa
    metta.run("\n".join(stmts))
    return pid


# ------------------------------------------------------------
# Evaluate consent (Python-grounded check as canonical)
# ------------------------------------------------------------
def check_consent(pid):
    log(f"\nChecking consent for {pid} ...")
    
    # --- Python-grounded check (deterministic) ---
    consent = python_has_consent(pid)
    
    # MeTTa's view for debugging (advisory)
    me_unresolved = metta.run(f"(HasUnresolvedObjection {pid})")
    me_consent = metta.run(f"(HasConsent {pid})")
    
    if args.verbose:
        log(f"[DEBUG] pid={pid} python_unresolved={python_has_unresolved(pid)} python_consent={consent}")
        log(f"[DEBUG] metta_unresolved={me_unresolved} metta_consent={me_consent}")
    
    # Use Python consent as the canonical decision
    return consent


# ------------------------------------------------------------
# Simulation Driver
# ------------------------------------------------------------
def simulate(folder):
    # Reset MeTTa interpreter and clear facts for clean state
    global metta, proposal_facts
    metta = MeTTa()
    proposal_facts.clear()
    load_rules()
    
    files = glob.glob(folder + "/*.json")
    if not files:
        print("No JSON files found in folder:", folder)
        return {}

    results = {}
    for f in files:
        pid = assert_proposal_and_record(f)
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
