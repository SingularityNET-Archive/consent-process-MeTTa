# Consent Process MeTTa

A consent evaluation system that uses [MeTTa](https://github.com/trueagi-io/hyperon-experimental) (Meta Type Theory) for declarative rule-based reasoning, combined with deterministic Python checks for reliable consent decisions.

## Overview

This project evaluates budget proposals for consent based on unresolved objections. It uses MeTTa for pattern matching and rule-based reasoning, while maintaining a Python-side canonical store of facts for deterministic, reliable consent decisions.

**Key Features:**
- ✅ **Dual evaluation system**: MeTTa for pattern/routing, Python for canonical decisions
- ✅ **Deterministic consent checks**: Python-side facts ensure reliable results
- ✅ **Interactive web interface**: Streamlit app for easy proposal evaluation
- ✅ **Command-line interface**: Batch processing via `sim.py`
- ✅ **Comprehensive debugging**: View both MeTTa and Python evaluation results

## Architecture

### Hybrid Approach: MeTTa + Python

The system uses a hybrid architecture to address the brittleness of MeTTa's negation semantics:

1. **MeTTa Rules**: Define declarative patterns for objections and consent
2. **Python Facts Store**: Maintains canonical state `{ pid: { "raised": set((oid, reviewer)), "resolved": set(oid) } }`
3. **Deterministic Checks**: Python functions compute consent reliably
4. **Advisory MeTTa Queries**: MeTTa results shown for debugging/comparison

This approach ensures:
- **Reliability**: Python checks are deterministic and don't depend on MeTTa's negation semantics
- **Transparency**: Both MeTTa and Python results are visible for comparison
- **Flexibility**: MeTTa can be extended for complex pattern matching while Python handles simple existence checks

### Consent Logic

A proposal has **consent** when:
- The proposal exists (is a `BudgetProposal`)
- There are **no unresolved objections**

An objection is **unresolved** when:
- It has been raised (`ObjectionRaised P O R`)
- It has **not** been resolved (`not (ObjectionResolved P O)`)

## Installation

### Prerequisites

- Python 3.12+
- pip

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd consent-process-MeTTa
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install hyperon streamlit
   ```

## Usage

### Option 1: Streamlit Web Interface

Launch the interactive web application:

```bash
streamlit run streamlit_app.py
```

The app will open in your browser. You can:
- **Upload JSON files**: Use the file uploader to add proposal files
- **Load sample proposals**: Click the button to load examples from `proposals/` folder
- **View results**: See consent status with expandable details for each proposal
- **Inspect evaluation**: View both Python (canonical) and MeTTa (advisory) results

### Option 2: Command-Line Interface

Process proposals from a folder:

```bash
python sim.py proposals/
```

With verbose debugging output:

```bash
python sim.py proposals/ -v
```

## Proposal JSON Format

Each proposal must be a JSON file with the following structure:

```json
{
  "id": "ProposalID",
  "submitter": "SubmitterName",
  "reviewers": ["Reviewer1", "Reviewer2"],
  "objections": [
    {
      "id": "OBJ1",
      "reviewer": "ReviewerName",
      "relevance": "financial",
      "reason": "Missing ROI calculation",
      "impact": "medium",
      "suggestion": "Add ROI analysis",
      "resolved": false
    }
  ]
}
```

### Required Fields

- `id` (string): Unique proposal identifier
- `submitter` (string): Name of the person submitting the proposal
- `reviewers` (array of strings): List of reviewers
- `objections` (array): List of objection objects (can be empty)

### Objection Object Fields

- `id` (string): Unique objection identifier
- `reviewer` (string): Name of reviewer who raised the objection
- `resolved` (boolean): Whether the objection has been resolved
- `reason` (string, optional): Reason for the objection
- `relevance` (string, optional): Relevance category
- `impact` (string, optional): Impact level
- `suggestion` (string, optional): Suggested resolution

### Example Proposals

See the `proposals/` folder for example files:
- `proposal.json` - Basic proposal with one unresolved objection
- `proposal_marketing_2025.json` - Proposal with no objections (has consent)
- `proposal_research_upgrade.json` - Proposal with unresolved objection
- `proposal_facilities_expansion.json` - Proposal with mixed resolved/unresolved objections

## MeTTa Rules

The system uses canonical MeTTa rules defined in both `streamlit_app.py` and `sim.py`:

```metta
;; Type Declarations
(: BudgetProposal P)
(: Proposal P)
(: Objection O)
(: Reviewer R)

;; Core Relations
(SubmittedBy P R)
(ReviewedBy P R)

;; Canonical objection facts
(ObjectionRaised P O R)
(ObjectionResolved P O)

;; Derived predicates
(HasUnresolvedObjection P) :-
    (ObjectionRaised P O R)
    (not (ObjectionResolved P O))

(HasConsent P) :-
    (BudgetProposal P)
    (not (HasUnresolvedObjection P))
```

### Predicate Signatures

- `(ObjectionRaised P O R)`: Proposal `P` has objection `O` raised by reviewer `R`
- `(ObjectionResolved P O)`: Proposal `P` has objection `O` resolved
- `(HasUnresolvedObjection P)`: Proposal `P` has at least one unresolved objection
- `(HasConsent P)`: Proposal `P` has consent (no unresolved objections)

## How It Works

### Processing Flow

1. **Load Rules**: MeTTa rules are loaded into the interpreter
2. **Parse Proposal**: JSON is parsed and validated
3. **Assert Facts**: 
   - MeTTa facts are asserted: `(BudgetProposal P)`, `(ObjectionRaised P O R)`, etc.
   - Python facts are stored: `proposal_facts[pid]["raised"]` and `proposal_facts[pid]["resolved"]`
4. **Evaluate Consent**:
   - **Python check** (canonical): `python_has_consent(pid)` computes deterministically
   - **MeTTa query** (advisory): `(HasConsent P)` for comparison/debugging
5. **Display Results**: Both results shown, Python decision is final

### Python Deterministic Functions

```python
def python_has_unresolved(pid):
    """Check if proposal has unresolved objections."""
    facts = proposal_facts.get(pid, {"raised": set(), "resolved": set()})
    raised_oids = {oid for (oid, _) in facts["raised"]}
    unresolved = raised_oids - facts["resolved"]
    return len(unresolved) > 0

def python_has_consent(pid):
    """Check if proposal has consent (no unresolved objections)."""
    return not python_has_unresolved(pid)
```

## Why This Architecture?

### Problem: MeTTa Negation Brittleness

MeTTa's `(not ...)` negation can be fragile when:
- Predicate arity mismatches cause rules to never match
- Facts aren't asserted correctly
- Interpreter state leaks between runs

### Solution: Python as Single Source of Truth

- **Python facts store**: Maintains exact state of raised/resolved objections
- **Deterministic checks**: Simple set operations (no negation semantics)
- **MeTTa for patterns**: Use MeTTa for complex pattern matching, not simple existence checks
- **Advisory queries**: MeTTa results shown for debugging but not used for final decision

## Example Output

### Streamlit App

```
✅ Consent Evaluation Results

✅ Marketing2025 → Approved
📄 Proposal JSON for Marketing2025 [expandable]
🔍 MeTTa Evaluation Details for Marketing2025 [expandable]
  - Python has_consent: ✅ True
  - MeTTa HasConsent: ✅ True (advisory)

❌ ResearchUpgrade → Not Approved
📄 Proposal JSON for ResearchUpgrade [expandable]
🔍 MeTTa Evaluation Details for ResearchUpgrade [expandable]
  - Python has_consent: ❌ False
  - Unresolved objections: 1
```

### CLI Output

```bash
$ python sim.py proposals/ -v

===== CONSENT EVALUATION RESULTS =====
Marketing2025              => True
ResearchUpgrade            => False
FacilitiesExpansion        => False
```

## Troubleshooting

### MeTTa Returns True When It Shouldn't

If you see incorrect MeTTa results:
1. Check predicate signatures match exactly: `(ObjectionRaised P O R)` not `(ObjectionRaised C P O R)`
2. Verify facts are asserted correctly
3. **Trust the Python result** - it's the canonical decision
4. Use verbose mode (`-v`) to see debugging output

### Interpreter State Issues

The system resets the MeTTa interpreter:
- **Streamlit**: On each file upload
- **CLI**: At the start of each simulation run

This prevents state leakage between runs.

## Development

### Project Structure

```
consent-process-MeTTa/
├── streamlit_app.py      # Streamlit web interface
├── sim.py                # CLI batch processor
├── proposals/            # Example proposal JSON files
│   ├── proposal.json
│   ├── proposal_marketing_2025.json
│   ├── proposal_research_upgrade.json
│   └── proposal_facilities_expansion.json
└── README.md             # This file
```

### Key Functions

**streamlit_app.py:**
- `load_rules(metta_instance)`: Load canonical MeTTa rules
- `assert_proposal_and_record()`: Parse JSON, assert facts, store in Python
- `python_has_unresolved(pid)`: Check for unresolved objections
- `python_has_consent(pid)`: Check for consent (canonical decision)

**sim.py:**
- `load_rules()`: Load MeTTa rules
- `assert_proposal_and_record(path)`: Process proposal file
- `check_consent(pid)`: Evaluate consent (uses Python as canonical)
- `simulate(folder)`: Batch process proposals

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Acknowledgments

- Built with [MeTTa/Hyperon](https://github.com/trueagi-io/hyperon-experimental)
- Web interface powered by [Streamlit](https://streamlit.io/)
