import streamlit as st
import json
import os
import glob
from hyperon import MeTTa

st.set_page_config(page_title="MeTTa Consent Simulation", layout="wide")

st.title("MeTTa Consent Simulation")
st.write("Upload proposal JSON files and evaluate consent across nested circles/domains.")

# Canonical Python store of facts for deterministic checks
# { pid: { "raised": set((oid, reviewer)), "resolved": set(oid) } }
if 'proposal_facts' not in st.session_state:
    st.session_state.proposal_facts = {}

# Canonical MeTTa rules
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

# Load MeTTa rules function
def load_rules(metta_instance):
    """Load canonical rules into MeTTa interpreter."""
    metta_instance.run(CANONICAL_RULES)

# Initialize MeTTa interpreter with error handling
try:
    metta = MeTTa()
    load_rules(metta)
    st.success("MeTTa interpreter initialized successfully!")
    
    # Store rules for display
    st.session_state.metta_rules = CANONICAL_RULES
    
except Exception as e:
    st.error(f"Error initializing MeTTa: {e}")
    st.stop()

# Display MeTTa rules
with st.expander("📜 MeTTa Rules", expanded=False):
    st.code(st.session_state.get('metta_rules', ''), language='lisp')
    st.markdown("""
    **Rule Logic:**
    - `HasUnresolvedObjection P` is true if there exists an objection raised for proposal P that has not been resolved
    - `HasConsent P` is true if proposal P exists AND there are no unresolved objections
    """)

# Show instructions
with st.expander("📋 Instructions & Example Format", expanded=False):
    st.markdown("""
    **How to use:**
    1. Upload one or more JSON proposal files using the file uploader below
    2. Or click "Load Sample Proposals" to load examples from the `proposals/` folder
    3. The app will evaluate consent based on unresolved objections
    
    **Expected JSON format:**
    ```json
    {
        "id": "ProposalID",
        "submitter": "SubmitterName",
        "domains": ["domain1", "domain2"],
        "objections": [
            {
                "id": "OBJ1",
                "circle": "CircleName",
                "reviewer": "ReviewerName",
                "resolved": false
            }
        ]
    }
    ```
    """)

# Load sample proposals button
if st.button("📁 Load Sample Proposals from `proposals/` folder"):
    proposal_files = glob.glob("proposals/*.json")
    if proposal_files:
        st.info(f"Found {len(proposal_files)} proposal file(s) in the proposals folder")
        # Store file paths in session state
        if 'sample_files' not in st.session_state:
            st.session_state.sample_files = proposal_files
    else:
        st.warning("No JSON files found in the `proposals/` folder")

uploaded_files = st.file_uploader("Upload JSON Proposal Files", accept_multiple_files=True, type=["json"])

results = {}
proposal_details = {}  # Store detailed info for each proposal

# Python-side deterministic consent check functions
def python_has_unresolved(pid):
    """Deterministic check for unresolved objections using Python facts."""
    facts = st.session_state.proposal_facts.get(pid, {"raised": set(), "resolved": set()})
    raised_oids = {oid for (oid, _) in facts["raised"]}
    unresolved = raised_oids - facts["resolved"]
    return len(unresolved) > 0

def python_has_consent(pid):
    """Deterministic check for consent: consent when there are NO unresolved objections."""
    return not python_has_unresolved(pid)

# Process uploaded proposals
def assert_proposal_and_record(file_or_path, is_file_path=False):
    try:
        if is_file_path:
            # Check if file is empty
            if os.path.getsize(file_or_path) == 0:
                return None, None, f"File is empty: {file_or_path}", None
            with open(file_or_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return None, None, f"File is empty: {file_or_path}", None
                data = json.loads(content)
        else:
            content = file_or_path.read().decode('utf-8').strip()
            if not content:
                return None, None, f"File is empty: {file_or_path.name}", None
            data = json.loads(content)
        
        pid = data.get("id", "UnknownProposal")
        title = data.get("title", pid)  # Use title if available, fallback to id
        # Handle both "submitter" and "author" fields
        submitter = data.get("submitter") or data.get("author", "UnknownSubmitter")
        reviewers = data.get("reviewers", [])
        objections = data.get("objections", [])

        # Build MeTTa statements with canonical predicate signatures
        stmts = []
        stmts.append(f"(BudgetProposal {pid})")
        stmts.append(f"(SubmittedBy {pid} {submitter})")

        for r in reviewers:
            stmts.append(f"(Reviewer {r})")
            stmts.append(f"(ReviewedBy {pid} {r})")

        # Prepare Python canonical store
        if pid not in st.session_state.proposal_facts:
            st.session_state.proposal_facts[pid] = {"raised": set(), "resolved": set()}

        for obj in objections:
            oid = obj.get("id")
            reviewer = obj.get("reviewer", "UnknownReviewer")

            # Assert canonical MeTTa facts: (ObjectionRaised P O R)
            stmts.append(f"(ObjectionRaised {pid} {oid} {reviewer})")

            if obj.get("resolved", False):
                stmts.append(f"(ObjectionResolved {pid} {oid})")
                st.session_state.proposal_facts[pid]["resolved"].add(oid)
            else:
                st.session_state.proposal_facts[pid]["raised"].add((oid, reviewer))

        # Assert statements into MeTTa
        metta.run("\n".join(stmts))

        # --- Python-grounded check (deterministic) ---
        consent = python_has_consent(pid)
        
        # MeTTa's view for debugging (advisory)
        unresolved_query = f"(HasUnresolvedObjection {pid})"
        consent_query = f"(HasConsent {pid})"
        me_unresolved = metta.run(unresolved_query)
        me_consent = metta.run(consent_query)
        
        # Use Python consent as the canonical decision
        approval = consent
        
        # Store details for display
        details = {
            'facts': stmts,
            'unresolved_query': unresolved_query,
            'unresolved_result': me_unresolved,
            'consent_query': consent_query,
            'consent_result': me_consent,
            'approval': approval,
            'python_unresolved': python_has_unresolved(pid),
            'python_consent': consent,
            'objections': objections,
            'reviewers': reviewers,
            'submitter': submitter,
            'title': title,
            'proposal_json': data  # Store original JSON data
        }
        
        return pid, approval, None, details
    except json.JSONDecodeError as e:
        filename = file_or_path if is_file_path else file_or_path.name
        return None, None, f"Invalid JSON in {filename}: {str(e)}", None
    except Exception as e:
        filename = file_or_path if is_file_path else file_or_path.name
        return None, None, f"Error processing {filename}: {str(e)}", None

# Reset MeTTa interpreter when files are uploaded (avoid state leakage)
if uploaded_files:
    # Reset interpreter and reload rules for clean state
    metta = MeTTa()
    load_rules(metta)
    st.session_state.proposal_facts.clear()

# Process uploaded files
if uploaded_files:
    with st.spinner("Processing uploaded files..."):
        for file in uploaded_files:
            pid, consent, error, details = assert_proposal_and_record(file)
            if error:
                st.error(f"Error processing {file.name}: {error}")
            else:
                results[pid] = consent
                if details:
                    proposal_details[pid] = details

# Process sample files from folder
if 'sample_files' in st.session_state and st.session_state.sample_files:
    with st.spinner("Processing sample proposals..."):
        for file_path in st.session_state.sample_files:
            pid, consent, error, details = assert_proposal_and_record(file_path, is_file_path=True)
            if error:
                st.error(f"Error processing {file_path}: {error}")
            else:
                results[pid] = consent
                if details:
                    proposal_details[pid] = details

# Display results
if results:
    st.subheader("✅ Consent Evaluation Results")
    
    # Create a mapping of titles to proposal IDs for the dropdown
    title_to_pid = {}
    pid_list = []
    title_list = []
    
    for pid in results.keys():
        title = pid
        if pid in proposal_details:
            title = proposal_details[pid].get('title', pid)
        title_to_pid[title] = pid
        pid_list.append(pid)
        title_list.append(title)
    
    # Display summary table
    st.markdown("### Summary")
    summary_data = []
    for pid, status in results.items():
        title = pid
        if pid in proposal_details:
            title = proposal_details[pid].get('title', pid)
        status_icon = "✅" if status else "❌"
        status_text = "Approved" if status else "Not Approved"
        summary_data.append({
            "Title": title,
            "Status": f"{status_icon} {status_text}",
            "ID": pid
        })
    
    # Display all proposals in a summary view
    for pid, status in results.items():
        title = pid
        if pid in proposal_details:
            title = proposal_details[pid].get('title', pid)
        status_icon = "✅" if status else "❌"
        status_text = "Approved" if status else "Not Approved"
        st.write(f"{status_icon} **{title}** → {status_text}")
    
    st.markdown("---")
    
    # Dropdown to select a proposal for detailed view
    if len(title_list) > 0:
        selected_title = st.selectbox(
            "Select a proposal to view details:",
            options=title_list,
            index=0,
            key="proposal_selector"
        )
        
        selected_pid = title_to_pid[selected_title]
        
        if selected_pid in proposal_details:
            details = proposal_details[selected_pid]
            
            # Display proposal JSON in expander
            with st.expander(f"📄 Proposal JSON for {selected_title}", expanded=False):
                st.json(details.get('proposal_json', {}))
            
            with st.expander(f"🔍 MeTTa Evaluation Details for {selected_title}", expanded=False):
                # Proposal info
                st.markdown("### Proposal Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Submitter:** {details['submitter']}")
                    st.write(f"**Reviewers:** {', '.join(details['reviewers'])}")
                with col2:
                    st.write(f"**Objections:** {len(details['objections'])}")
                    unresolved_count = sum(1 for obj in details['objections'] if not obj.get('resolved', False))
                    st.write(f"**Unresolved:** {unresolved_count}")
                
                # Asserted facts
                st.markdown("### Asserted MeTTa Facts")
                st.code("\n".join(details['facts']), language='lisp')
                
                # Python deterministic check (canonical)
                st.markdown("### Python Deterministic Check (Canonical)")
                python_unresolved = details.get('python_unresolved', False)
                python_consent = details.get('python_consent', False)
                st.write(f"**Python `has_unresolved`:** {'✅ True' if python_unresolved else '❌ False'}")
                st.write(f"**Python `has_consent`:** {'✅ True' if python_consent else '❌ False'}")
                st.info("💡 **This is the canonical decision** - computed deterministically from Python facts.")
                
                # MeTTa queries and results (advisory/debugging)
                st.markdown("### MeTTa Query Evaluation (Advisory)")
                
                # Unresolved objection query
                st.markdown("#### Step 1: Check for Unresolved Objections")
                st.code(details['unresolved_query'], language='lisp')
                unresolved_bool = bool(details['unresolved_result'])
                unresolved_display = "✅ True (has unresolved objections)" if unresolved_bool else "❌ False (no unresolved objections)"
                st.write(f"**MeTTa Result:** {unresolved_display}")
                if details['unresolved_result']:
                    st.json(details['unresolved_result'])
                else:
                    st.write("*Empty result (no matches)*")
                
                # Consent query
                st.markdown("#### Step 2: Check for Consent")
                st.code(details['consent_query'], language='lisp')
                consent_bool = bool(details['consent_result'])
                consent_display = "✅ True (has consent)" if consent_bool else "❌ False (no consent)"
                st.write(f"**MeTTa Result:** {consent_display}")
                if details['consent_result']:
                    st.json(details['consent_result'])
                else:
                    st.write("*Empty result (no matches)*")
                
                # Reasoning - use Python canonical decision
                st.markdown("### Reasoning")
                actual_unresolved_count = sum(1 for obj in details['objections'] if not obj.get('resolved', False))
                
                if actual_unresolved_count > 0:
                    st.warning(f"❌ **No Consent**: Proposal {selected_title} has {actual_unresolved_count} unresolved objection(s).")
                    st.markdown(f"**Python check:** `python_has_unresolved({selected_pid})` = True → `python_has_consent({selected_pid})` = False")
                    st.markdown(f"**MeTTa rule (advisory):** `(HasConsent P) :- (BudgetProposal P) (not (HasUnresolvedObjection P))`")
                else:
                    st.success(f"✅ **Has Consent**: Proposal {selected_title} exists and has no unresolved objections.")
                    st.markdown(f"**Python check:** `python_has_unresolved({selected_pid})` = False → `python_has_consent({selected_pid})` = True")
                    st.markdown(f"**MeTTa rule (advisory):** `(HasConsent P) :- (BudgetProposal P) (not (HasUnresolvedObjection P))`")
                
                # Objections breakdown
                if details['objections']:
                    st.markdown("### Objections Breakdown")
                    for obj in details['objections']:
                        resolved_icon = "✅" if obj.get('resolved', False) else "❌"
                        resolved_text = "Resolved" if obj.get('resolved', False) else "Unresolved"
                        st.write(f"{resolved_icon} **{obj.get('id', 'Unknown')}** - {resolved_text}")
                        if obj.get('reason'):
                            st.caption(f"   Reason: {obj.get('reason')}")
        
        st.markdown("---")
elif not uploaded_files and 'sample_files' not in st.session_state:
    st.info("👆 Upload JSON proposal files above or click 'Load Sample Proposals' to get started.")
