import streamlit as st
import json
import os
import glob
from hyperon import MeTTa

st.set_page_config(page_title="MeTTa Consent Simulation", layout="wide")

st.title("MeTTa Consent Simulation")
st.write("Upload proposal JSON files and evaluate consent across nested circles/domains.")

# Initialize MeTTa interpreter with error handling
try:
    metta = MeTTa()
    
    # Load MeTTa rules - use the same format as sim.py for compatibility
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
        metta.run(rules)
    
    load_rules()
    st.success("MeTTa interpreter initialized successfully!")
    
    # Store rules for display
    st.session_state.metta_rules = r'''
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

# Process uploaded proposals
def process_proposal(file_or_path, is_file_path=False):
    try:
        if is_file_path:
            # Check if file is empty
            if os.path.getsize(file_or_path) == 0:
                return None, None, f"File is empty: {file_or_path}"
            with open(file_or_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return None, None, f"File is empty: {file_or_path}"
                data = json.loads(content)
        else:
            content = file_or_path.read().decode('utf-8').strip()
            if not content:
                return None, None, f"File is empty: {file_or_path.name}"
            data = json.loads(content)
        
        pid = data.get("id", "UnknownProposal")
        submitter = data.get("submitter", "UnknownSubmitter")
        reviewers = data.get("reviewers", [])
        objections = data.get("objections", [])

        # Build MeTTa statements exactly like sim.py
        stmts = []
        stmts.append(f"(BudgetProposal {pid})")
        stmts.append(f"(SubmittedBy {pid} {submitter})")

        for r in reviewers:
            stmts.append(f"(Reviewer {r})")
            stmts.append(f"(ReviewedBy {pid} {r})")

        for obj in objections:
            oid = obj.get("id")
            reviewer = obj.get("reviewer", "UnknownReviewer")

            relevance = obj.get("relevance", "none")
            reason = obj.get("reason", "none")
            impact = obj.get("impact", "none")
            suggestion = obj.get("suggestion", "none")

            # Encode objection as a structured MeTTa term (like sim.py)
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

        # Load facts into MeTTa (same as sim.py)
        metta.run("\n".join(stmts))

        # Query MeTTa for consent and intermediate queries
        unresolved_query = f"(HasUnresolvedObjection {pid})"
        consent_query = f"(HasConsent {pid})"
        
        unresolved_result = metta.run(unresolved_query)
        consent_result = metta.run(consent_query)
        
        # MeTTa returns empty list if query doesn't match, non-empty if it does
        # Empty = False (no consent), non-empty = True (has consent)
        approval = bool(consent_result)
        
        # Store details for display
        details = {
            'facts': stmts,
            'unresolved_query': unresolved_query,
            'unresolved_result': unresolved_result,
            'consent_query': consent_query,
            'consent_result': consent_result,
            'approval': approval,
            'objections': objections,
            'reviewers': reviewers,
            'submitter': submitter
        }
        
        return pid, approval, None, details
    except json.JSONDecodeError as e:
        filename = file_or_path if is_file_path else file_or_path.name
        return None, None, f"Invalid JSON in {filename}: {str(e)}", None
    except Exception as e:
        filename = file_or_path if is_file_path else file_or_path.name
        return None, None, f"Error processing {filename}: {str(e)}", None

# Process uploaded files
if uploaded_files:
    with st.spinner("Processing uploaded files..."):
        for file in uploaded_files:
            pid, consent, error, details = process_proposal(file)
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
            pid, consent, error, details = process_proposal(file_path, is_file_path=True)
            if error:
                st.error(f"Error processing {file_path}: {error}")
            else:
                results[pid] = consent
                if details:
                    proposal_details[pid] = details

# Display results
if results:
    st.subheader("✅ Consent Evaluation Results")
    for pid, status in results.items():
        status_icon = "✅" if status else "❌"
        status_text = "Approved" if status else "Not Approved"
        
        # Main result
        st.write(f"{status_icon} **{pid}** → {status_text}")
        
        # Show MeTTa evaluation details if available
        if pid in proposal_details:
            details = proposal_details[pid]
            
            with st.expander(f"🔍 MeTTa Evaluation Details for {pid}", expanded=False):
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
                
                # MeTTa queries and results
                st.markdown("### MeTTa Query Evaluation")
                
                # Unresolved objection query
                st.markdown("#### Step 1: Check for Unresolved Objections")
                st.code(details['unresolved_query'], language='lisp')
                unresolved_bool = bool(details['unresolved_result'])
                unresolved_display = "✅ True (has unresolved objections)" if unresolved_bool else "❌ False (no unresolved objections)"
                st.write(f"**Result:** {unresolved_display}")
                if details['unresolved_result']:
                    st.json(details['unresolved_result'])
                else:
                    st.write("*Empty result (no matches)*")
                
                # Consent query
                st.markdown("#### Step 2: Check for Consent")
                st.code(details['consent_query'], language='lisp')
                consent_bool = bool(details['consent_result'])
                consent_display = "✅ True (has consent)" if consent_bool else "❌ False (no consent)"
                st.write(f"**Result:** {consent_display}")
                if details['consent_result']:
                    st.json(details['consent_result'])
                else:
                    st.write("*Empty result (no matches)*")
                
                # Reasoning - use actual approval status and objection data
                st.markdown("### Reasoning")
                actual_unresolved_count = sum(1 for obj in details['objections'] if not obj.get('resolved', False))
                
                if actual_unresolved_count > 0:
                    st.warning(f"❌ **No Consent**: Proposal {pid} has {actual_unresolved_count} unresolved objection(s), so `HasConsent` evaluates to False.")
                    st.markdown(f"According to the MeTTa rule: `(HasConsent P) :- (BudgetProposal P) (not (HasUnresolvedObjection P))`")
                    st.markdown(f"Since `HasUnresolvedObjection {pid}` is True (there are unresolved objections), `HasConsent {pid}` evaluates to False.")
                else:
                    st.success(f"✅ **Has Consent**: Proposal {pid} exists and has no unresolved objections, so `HasConsent` evaluates to True.")
                    st.markdown(f"According to the MeTTa rule: `(HasConsent P) :- (BudgetProposal P) (not (HasUnresolvedObjection P))`")
                    st.markdown(f"Since `HasUnresolvedObjection {pid}` is False (no unresolved objections), `HasConsent {pid}` evaluates to True.")
                
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
